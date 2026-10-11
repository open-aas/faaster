"""
TimescaleDatabase contra um TimescaleDB real: criação nos dois modos,
reconciliação a cada partida (views e policies) e agregados corretos.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import json

import pytest

from faaster.hda.buffer import WindowResult
from faaster.hda.policies import HDAFunction, extract_policy
from faaster.infra.database_timescale import view_definition


TABLE = "0f3a9c1d2e4b5a6978c0d1e2f3a4b5c6"  # como build_table_name: md5, pode começar com dígito
DOUBLE = 11


def ext(name, value):
    return SimpleNamespace(name=name, value=value)


def sample_policy(levels="1min,1hour,1day", **retention):
    exts = [ext("faaster:hda:levels", levels)]
    exts += [ext(f"faaster:hda:retention:{owner}", kept) for owner, kept in retention.items()]
    return extract_policy(exts)


def aggregate_policy(function="mean", window="15min"):
    return extract_policy([
        ext("faaster:hda:mode", "aggregate"),
        ext("faaster:hda:window", window),
        ext("faaster:hda:function", function),
    ])


async def create(db, policy, table=TABLE):
    await db.create_node_table(
        table_name=table,
        index=f"urn:sm::{table}",
        id_short="Voltage",
        submodel="Energy",
        submodel_id="urn:sm",
        path="Energy/Voltage/Value",
        semantic_id=None,
        policy=policy,
    )


async def fetch(db, sql, *args):
    async with db._pool.acquire() as conn:
        return await conn.fetch(sql, *args)


async def fetchval(db, sql, *args):
    async with db._pool.acquire() as conn:
        return await conn.fetchval(sql, *args)


async def views(db, table=TABLE):
    rows = await fetch(db, """
        SELECT view_name, materialized_only
        FROM timescaledb_information.continuous_aggregates
        WHERE view_name LIKE $1
    """, f"{table}\\_%")
    return {row["view_name"]: row["materialized_only"] for row in rows}


async def oid(db, relation):
    return await fetchval(db, "SELECT to_regclass($1)::oid", f'"{relation}"')


async def job_config(db, proc_name, relation):
    """config das policies (retenção/atualização) de uma hypertable ou view."""
    rows = await fetch(db, """
        SELECT config FROM timescaledb_information.jobs
        WHERE proc_name = $1 AND hypertable_name = $2
    """, proc_name, relation)
    return [json.loads(row["config"]) for row in rows]


async def retention(db, relation):
    configs = await job_config(db, "policy_retention", relation)
    assert len(configs) <= 1
    return configs[0]["drop_after"] if configs else None


def hour_ago() -> datetime:
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return now - timedelta(hours=2)


async def insert_two_minutes(db, start, table=TABLE):
    """Valores 0..119, um por segundo."""
    for second in range(120):
        await db.insert(table, float(second), start + timedelta(seconds=second), DOUBLE)


# -----------------------------------------------------------------------------
# Modo sample
# -----------------------------------------------------------------------------

async def test_sample_policy_creates_views_and_policies(timescale_db):
    await create(timescale_db, sample_policy())

    assert await views(timescale_db) == {
        f"{TABLE}_1min": False,   # agregação em tempo real
        f"{TABLE}_1hour": False,
        f"{TABLE}_1day": False,
    }
    assert await retention(timescale_db, TABLE) == "30 days"
    assert await retention(timescale_db, f"{TABLE}_1min") == "1 year"
    assert await retention(timescale_db, f"{TABLE}_1hour") == "5 years"
    assert await retention(timescale_db, f"{TABLE}_1day") is None

    [refresh] = await job_config(timescale_db, "policy_refresh_continuous_aggregate", f"{TABLE}_1day")
    assert (refresh["start_offset"], refresh["end_offset"]) == ("4 days", "00:01:00")

    compressed = await fetchval(timescale_db, """
        SELECT compression_enabled FROM timescaledb_information.hypertables WHERE hypertable_name = $1
    """, TABLE)
    assert compressed is True


async def test_levels_are_exact_aggregates_of_raw_data(timescale_db):
    # dados antes das views: o job de atualização roda assim que a policy é
    # criada e não pode materializar um bucket pela metade
    await create(timescale_db, None)
    start = hour_ago()
    await insert_two_minutes(timescale_db, start)
    await create(timescale_db, sample_policy("1min,1hour"))

    async def check():
        minutes = await timescale_db.query(TABLE, start, start + timedelta(hours=1), 10, level="1min")
        assert [(r["bucket"], r["avg_value"], r["max_value"], r["min_value"], r["sample_count"]) for r in minutes] == [
            (start, 29.5, 59.0, 0.0, 60),
            (start + timedelta(minutes=1), 89.5, 119.0, 60.0, 60),
        ]
        [hour] = await timescale_db.query(TABLE, start, start + timedelta(hours=1), 10, level="1hour")
        # max/min/count reais, não das médias por minuto
        assert (hour["avg_value"], hour["max_value"], hour["min_value"], hour["sample_count"]) == (59.5, 119.0, 0.0, 120)

    await check()                      # tempo real e/ou já materializado
    await timescale_db.wait_backfills()
    await check()                      # todo o histórico materializado

    backfilled = await fetch(timescale_db, "SELECT backfilled_at FROM faaster_aggregates")
    assert all(row["backfilled_at"] is not None for row in backfilled)


async def test_restart_keeps_unchanged_views(timescale_db):
    policy = sample_policy()
    await create(timescale_db, policy)
    await timescale_db.wait_backfills()
    before = {view: await oid(timescale_db, view) for view in await views(timescale_db)}

    await create(timescale_db, policy)

    assert {view: await oid(timescale_db, view) for view in await views(timescale_db)} == before
    assert await retention(timescale_db, TABLE) == "30 days"
    assert len(await job_config(timescale_db, "policy_refresh_continuous_aggregate", f"{TABLE}_1min")) == 1


async def test_restart_with_compressed_chunks(timescale_db):
    await create(timescale_db, sample_policy())
    old = datetime.now(timezone.utc) - timedelta(days=20)
    await timescale_db.insert(TABLE, 1.0, old, DOUBLE)
    compressed = await fetch(timescale_db, f"""
        SELECT compress_chunk(chunk) FROM show_chunks('"{TABLE}"', older_than => INTERVAL '8 days') AS chunk
    """)
    assert compressed

    await create(timescale_db, sample_policy())

    rows = await timescale_db.query(TABLE, old - timedelta(seconds=1), old + timedelta(seconds=1), 10)
    assert [row["value"] for row in rows] == [1.0]


async def test_policy_change_recreates_only_what_changed(timescale_db):
    await create(timescale_db, None)
    start = hour_ago()
    await insert_two_minutes(timescale_db, start)
    await create(timescale_db, sample_policy())
    await timescale_db.wait_backfills()
    kept = {level: await oid(timescale_db, f"{TABLE}_{level}") for level in ("1min", "1hour")}

    await create(timescale_db, sample_policy("1min,15min,1hour", raw="90 days", **{"1min": "6 months"}))

    assert set(await views(timescale_db)) == {f"{TABLE}_1min", f"{TABLE}_15min", f"{TABLE}_1hour"}
    for level, view_oid in kept.items():
        assert await oid(timescale_db, f"{TABLE}_{level}") == view_oid
    assert await retention(timescale_db, TABLE) == "90 days"
    assert await retention(timescale_db, f"{TABLE}_1min") == "6 mons"
    assert await retention(timescale_db, f"{TABLE}_15min") is None

    # o level novo é reprocessado a partir do histórico raw
    await timescale_db.wait_backfills()
    [quarter] = await timescale_db.query(TABLE, start, start + timedelta(hours=1), 10, level="15min")
    assert quarter["sample_count"] == 120

    recorded = await fetch(timescale_db, "SELECT view_name FROM faaster_aggregates ORDER BY view_name")
    assert [row["view_name"] for row in recorded] == sorted(await views(timescale_db))


async def test_changed_definition_recreates_view(timescale_db):
    await create(timescale_db, sample_policy("1min"))
    before = await oid(timescale_db, f"{TABLE}_1min")
    async with timescale_db._pool.acquire() as conn:
        await conn.execute("UPDATE faaster_aggregates SET definition = 'old'")

    await create(timescale_db, sample_policy("1min"))

    assert await oid(timescale_db, f"{TABLE}_1min") != before
    assert await fetchval(timescale_db, "SELECT definition FROM faaster_aggregates") == view_definition("1min")


async def test_legacy_hierarchical_views_are_recreated(timescale_db):
    # views da versão anterior: 1hour calculada sobre a 1min, sem registro
    await create(timescale_db, None)
    async with timescale_db._pool.acquire() as conn:
        await conn.execute(f"""
            CREATE MATERIALIZED VIEW "{TABLE}_1min" WITH (timescaledb.continuous) AS
            SELECT time_bucket('1 minute', source_timestamp) AS bucket, AVG(value) AS avg_value
            FROM "{TABLE}" GROUP BY 1 WITH NO DATA;
        """)
        await conn.execute(f"""
            CREATE MATERIALIZED VIEW "{TABLE}_1hour" WITH (timescaledb.continuous) AS
            SELECT time_bucket('1 hour', bucket) AS hour_bucket, AVG(avg_value) AS avg_value
            FROM "{TABLE}_1min" GROUP BY 1 WITH NO DATA;
        """)

    start = hour_ago()
    await insert_two_minutes(timescale_db, start)

    await create(timescale_db, sample_policy("1min,1hour"))

    assert await views(timescale_db) == {f"{TABLE}_1min": False, f"{TABLE}_1hour": False}
    [hour] = await timescale_db.query(TABLE, start, start + timedelta(hours=1), 10, level="1hour")
    assert hour["max_value"] == 119.0


async def test_no_policy_removes_raw_retention(timescale_db):
    await create(timescale_db, sample_policy())
    await create(timescale_db, None)

    assert await retention(timescale_db, TABLE) is None


async def test_query_ranges_and_order(timescale_db):
    await create(timescale_db, None)
    start = hour_ago()
    for second in range(5):
        await timescale_db.insert(TABLE, float(second), start + timedelta(seconds=second), DOUBLE)

    def values(rows):
        return [row["value"] for row in rows]

    assert values(await timescale_db.query(TABLE, start + timedelta(seconds=3), None, 10)) == [3.0, 4.0]
    assert values(await timescale_db.query(TABLE, None, start + timedelta(seconds=1), 10, reverse=True)) == [1.0, 0.0]
    assert values(await timescale_db.query(TABLE, start, start + timedelta(seconds=4), 2, reverse=True)) == [4.0, 3.0]


# -----------------------------------------------------------------------------
# Modo aggregate
# -----------------------------------------------------------------------------

def window(bucket, value, count, last):
    return WindowResult(bucket=bucket, value=value, sample_count=count, last_timestamp=last)


@pytest.mark.parametrize("function, merged", [
    (HDAFunction.mean, 4.0),    # (2.0 * 1 + 5.0 * 2) / 3
    (HDAFunction.sum, 7.0),
    (HDAFunction.max, 5.0),
    (HDAFunction.min, 2.0),
    (HDAFunction.last, 2.0),    # a primeira gravação tem a amostra mais recente
])
async def test_late_window_is_merged(timescale_db, function, merged):
    await create(timescale_db, aggregate_policy(function.value))
    bucket = hour_ago()

    await timescale_db.insert_aggregate(TABLE, window(bucket, 2.0, 1, bucket + timedelta(minutes=14)), "15min", function)
    await timescale_db.insert_aggregate(TABLE, window(bucket, 5.0, 2, bucket + timedelta(minutes=3)), "15min", function)

    [row] = await timescale_db.query_aggregate(
        TABLE, bucket, bucket + timedelta(hours=1), 10, window="15min", function=function
    )
    assert row["value"] == pytest.approx(merged)
    assert row["sample_count"] == 3
    assert row["last_timestamp"] == bucket + timedelta(minutes=14)


async def test_aggregate_mode_keeps_one_row_per_window_and_function(timescale_db):
    await create(timescale_db, aggregate_policy("sum"))
    bucket = hour_ago()
    later = bucket + timedelta(minutes=15)

    await timescale_db.insert_aggregate(TABLE, window(bucket, 1.0, 1, bucket), "15min", HDAFunction.sum)
    await timescale_db.insert_aggregate(TABLE, window(later, 2.0, 1, later), "15min", HDAFunction.sum)
    await timescale_db.insert_aggregate(TABLE, window(bucket, 9.0, 1, bucket), "15min", HDAFunction.max)

    rows = await timescale_db.query_aggregate(
        TABLE, None, later, 10, window="15min", function=HDAFunction.sum, reverse=True
    )
    assert [(row["bucket"], row["value"]) for row in rows] == [(later, 2.0), (bucket, 1.0)]
    assert await retention(timescale_db, f"{TABLE}_agg") == "5 years"


async def test_mode_switch_keeps_the_other_mode_data(timescale_db):
    await create(timescale_db, None)
    start = hour_ago()
    await insert_two_minutes(timescale_db, start)
    await create(timescale_db, sample_policy("1min"))

    await create(timescale_db, aggregate_policy())
    await create(timescale_db, sample_policy("1min"))

    rows = await timescale_db.query(TABLE, start, start + timedelta(hours=1), 1000)
    assert len(rows) == 120
    assert set(await views(timescale_db)) == {f"{TABLE}_1min"}

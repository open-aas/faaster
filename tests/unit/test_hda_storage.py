"""
TimescaleHDAStorage com um IDatabase em memória: roteamento sample /
aggregate / virtual, janelas do modo aggregate e semântica do HistoryRead
(OPC 10000-11).
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Dict, List
from unittest.mock import AsyncMock

import pytest
from asyncua import ua

from faaster.hda import storage as storage_module
from faaster.hda.buffer import WindowResult
from faaster.hda.manager import HDAManager
from faaster.hda.policies import HDAFunction, extract_policy
from faaster.hda.storage import TimescaleHDAStorage, history_range
from faaster.interfaces.idatabase import IDatabase
from faaster.interfaces.types import FaasterVariantType
from faaster.parser.node_registry import NodeMetadata, NodeRegistry


T0 = datetime(2026, 10, 11, 10, 0, tzinfo=timezone.utc)
UNSPECIFIED = datetime(1601, 1, 1, tzinfo=timezone.utc)


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def ext(name, value):
    return SimpleNamespace(name=name, value=value)


class FakeDatabase(IDatabase):
    """Mesmo contrato do TimescaleDatabase, em memória."""

    def __init__(self) -> None:
        self.tables: Dict[str, dict] = {}
        self.raw: Dict[str, List[dict]] = {}
        self.levels: Dict[tuple, List[dict]] = {}
        self.windows: Dict[str, List[dict]] = {}
        self.fail_inserts = 0
        self.fail_raw_inserts = 0
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def bootstrap(self) -> None:
        pass

    async def create_node_table(self, table_name, policy, **metadata) -> None:
        self.tables[table_name] = dict(metadata, policy=policy)

    async def insert(self, table_name, value, source_timestamp, variant_type) -> None:
        if self.fail_raw_inserts:
            self.fail_raw_inserts -= 1
            raise ConnectionError("database offline")
        self.raw.setdefault(table_name, []).append(
            {"source_timestamp": source_timestamp, "value": float(value), "variant_type": variant_type}
        )

    async def insert_aggregate(self, table_name, result: WindowResult, window, function) -> None:
        if self.fail_inserts:
            self.fail_inserts -= 1
            raise ConnectionError("database offline")
        self.windows.setdefault(table_name, []).append(
            {"bucket": result.bucket, "value": result.value, "sample_count": result.sample_count,
             "last_timestamp": result.last_timestamp, "window": window, "function": function}
        )

    @staticmethod
    def _range(rows, column, start, end, limit, reverse):
        rows = [
            r for r in rows
            if (start is None or r[column] >= start) and (end is None or r[column] <= end)
        ]
        return sorted(rows, key=lambda r: r[column], reverse=reverse)[:limit]

    async def query(self, table_name, start, end, limit, level="raw", reverse=False):
        if level == "raw":
            return self._range(self.raw.get(table_name, []), "source_timestamp", start, end, limit, reverse)
        return self._range(self.levels.get((table_name, level), []), "bucket", start, end, limit, reverse)

    async def query_aggregate(self, table_name, start, end, limit, window, function, reverse=False):
        rows = [
            r for r in self.windows.get(table_name, [])
            if r["window"] == window and r["function"] == function
        ]
        return self._range(rows, "bucket", start, end, limit, reverse)


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


_next_id = iter(range(1, 10_000))


def register(registry, id_short, extensions=None, level="raw", raw_path=None):
    path = raw_path or f"Energy/{id_short}/Value"
    ua_node_id = ua.NodeId(next(_next_id), 2)
    metadata = NodeMetadata(
        # mesmo formato do NodeAdapter: str() do NodeId do asyncua
        node=SimpleNamespace(node_id=str(ua_node_id), ua_node_id=ua_node_id),
        path=path if level == "raw" else f"{path}@{level}",
        variant_type=FaasterVariantType.Double,
        id_short=id_short if level == "raw" else f"Value@{level}",
        submodel="Energy",
        submodel_id="urn:sm:energy",
        aggregation_policy=extract_policy(extensions) if level == "raw" else None,
        level=level,
    )
    registry.register(metadata)
    return metadata


def node_id(metadata) -> ua.NodeId:
    return metadata.node.ua_node_id


def sample(value, timestamp=None, vtype=ua.VariantType.Double, server_timestamp=None):
    return ua.DataValue(
        Value=ua.Variant(value, vtype),
        SourceTimestamp=timestamp,
        ServerTimestamp=server_timestamp,
    )


SAMPLE_POLICY = [ext("faaster:hda:levels", "1min,1hour")]
SUM_15MIN = [
    ext("faaster:hda:mode", "aggregate"),
    ext("faaster:hda:window", "15min"),
    ext("faaster:hda:function", "sum"),
]


@pytest.fixture
def db():
    return FakeDatabase()


@pytest.fixture
def registry():
    return NodeRegistry()


@pytest.fixture
def clock():
    return Clock(at(20))


@pytest.fixture
async def storage(db, registry, clock):
    hda = TimescaleHDAStorage(db=db, registry=registry, clock=clock)
    await hda.init()
    yield hda
    for task in [*hda._tasks, hda._writer]:
        task.cancel()


def table_of(storage_metadata):
    return storage_module._table_name(storage_metadata)


# -----------------------------------------------------------------------------
# Registro e gravação
# -----------------------------------------------------------------------------

async def test_new_historized_node_creates_table_with_policy(storage, db, registry):
    voltage = register(registry, "Voltage", SAMPLE_POLICY)

    await storage.new_historized_node(node_id(voltage), period=None)

    table = db.tables[table_of(voltage)]
    assert table["policy"].levels == ["1min", "1hour"]
    assert table["path"] == "Energy/Voltage/Value"
    assert table["semantic_id"] is None


async def test_virtual_node_has_no_table(storage, db, registry):
    register(registry, "Voltage", SAMPLE_POLICY)
    virtual = register(registry, "Voltage", level="1min")

    await storage.new_historized_node(node_id(virtual), period=None)
    await storage.save_node_value(node_id(virtual), sample(1.0, at(1)))

    assert db.tables == {}
    assert db.raw == {}


async def test_sample_mode_inserts_with_source_timestamp(storage, db, registry):
    voltage = register(registry, "Voltage", SAMPLE_POLICY)

    await storage.save_node_value(node_id(voltage), sample(220, at(1), ua.VariantType.Int32))
    await storage.drain()

    assert db.raw[table_of(voltage)] == [
        {"source_timestamp": at(1), "value": 220.0, "variant_type": ua.VariantType.Int32.value}
    ]


async def test_timestamp_falls_back_to_server_then_clock(storage, db, registry):
    plain = register(registry, "Plain")

    await storage.save_node_value(node_id(plain), sample(1.0, server_timestamp=at(2)))
    await storage.save_node_value(node_id(plain), sample(2.0))
    await storage.drain()

    assert [r["source_timestamp"] for r in db.raw[table_of(plain)]] == [at(2), at(20)]


@pytest.mark.parametrize("data_value", [
    sample("text", at(1), ua.VariantType.String),
    ua.DataValue(Value=ua.Variant(None, ua.VariantType.Null), SourceTimestamp=at(1)),
])
async def test_non_numeric_values_are_skipped(storage, db, registry, data_value):
    plain = register(registry, "Plain")

    await storage.save_node_value(node_id(plain), data_value)
    await storage.drain()

    assert db.raw == {}


async def test_repeated_values_are_all_stored_in_order(storage, db, registry):
    plain = register(registry, "Plain")

    for second in range(5):
        await storage.save_node_value(node_id(plain), sample(1.0, at(second / 60)))
    await storage.drain()

    assert [r["source_timestamp"] for r in db.raw[table_of(plain)]] == [at(s / 60) for s in range(5)]


async def test_failed_raw_insert_does_not_stop_the_writer(storage, db, registry):
    plain = register(registry, "Plain")
    db.fail_raw_inserts = 1

    await storage.save_node_value(node_id(plain), sample(1.0, at(1)))
    await storage.save_node_value(node_id(plain), sample(2.0, at(2)))
    await storage.drain()

    assert [r["value"] for r in db.raw[table_of(plain)]] == [2.0]


async def test_stop_is_idempotent(storage, db):
    await storage.stop()
    db.connected = True
    await storage.stop()

    assert db.connected is True


async def test_stop_writes_queued_samples(storage, db, registry):
    plain = register(registry, "Plain")
    await storage.save_node_value(node_id(plain), sample(1.0, at(1)))

    await storage.stop()

    assert [r["value"] for r in db.raw[table_of(plain)]] == [1.0]


# -----------------------------------------------------------------------------
# Modo aggregate
# -----------------------------------------------------------------------------

async def test_aggregate_mode_flushes_closed_windows(storage, db, registry, clock):
    energy = register(registry, "Energy", SUM_15MIN)
    await storage.new_historized_node(node_id(energy), period=None)

    for minute, value in [(1, 1.0), (14, 2.0), (16, 4.0)]:
        await storage.save_node_value(node_id(energy), sample(value, at(minute)))

    clock.now = at(15.1)
    await storage.flush(energy, table_of(energy))

    [window] = db.windows[table_of(energy)]
    assert (window["bucket"], window["value"], window["sample_count"]) == (at(0), 3.0, 2)
    assert (window["window"], window["function"]) == ("15min", HDAFunction.sum)
    # a janela das 10:15 continua aberta
    assert list(energy.buffer.buckets) == [at(15)]


async def test_failed_flush_is_retried_next_window(storage, db, registry, clock):
    energy = register(registry, "Energy", SUM_15MIN)
    await storage.save_node_value(node_id(energy), sample(1.0, at(1)))
    await storage.save_node_value(node_id(energy), sample(2.0, at(16)))

    db.fail_inserts = 1
    clock.now = at(15.1)
    await storage.flush(energy, table_of(energy))
    assert table_of(energy) not in db.windows

    clock.now = at(30.1)
    await storage.flush(energy, table_of(energy))

    assert [(w["bucket"], w["value"]) for w in db.windows[table_of(energy)]] == [(at(0), 1.0), (at(15), 2.0)]


async def test_window_loop_sleeps_until_clock_boundary(storage, registry, clock, monkeypatch):
    energy = register(registry, "Energy", SUM_15MIN)
    delays = []

    async def fake_sleep(seconds):
        delays.append(seconds)
        raise asyncio.CancelledError

    monkeypatch.setattr(storage_module.asyncio, "sleep", fake_sleep)
    clock.now = at(20)

    with pytest.raises(asyncio.CancelledError):
        await storage._aggregate_window_loop(energy, table_of(energy))

    # 10:20 → próxima fronteira 10:30, mais a folga
    assert delays == [pytest.approx(600 + storage_module._FLUSH_GRACE_SECONDS)]


async def test_window_loop_survives_database_errors(storage, db, registry, clock, monkeypatch):
    energy = register(registry, "Energy", SUM_15MIN)
    await storage.save_node_value(node_id(energy), sample(1.0, at(1)))
    db.fail_inserts = 1
    calls = 0

    async def fake_sleep(seconds):
        nonlocal calls
        calls += 1
        clock.now += timedelta(minutes=15)
        if calls == 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(storage_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await storage._aggregate_window_loop(energy, table_of(energy))

    assert [w["value"] for w in db.windows[table_of(energy)]] == [1.0]


async def test_stop_persists_open_window_and_disconnects(storage, db, registry, clock):
    energy = register(registry, "Energy", SUM_15MIN)
    await storage.new_historized_node(node_id(energy), period=None)
    task = energy.buffer.task
    await storage.save_node_value(node_id(energy), sample(5.0, at(16)))

    await storage.stop()

    assert task.cancelled()
    assert [(w["bucket"], w["value"]) for w in db.windows[table_of(energy)]] == [(at(15), 5.0)]
    assert db.connected is False


# -----------------------------------------------------------------------------
# HistoryRead
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("start, end, expected", [
    (at(1), at(5), (at(1), at(5), False)),
    (at(5), at(1), (at(1), at(5), True)),
    (at(1), UNSPECIFIED, (at(1), None, False)),
    (at(1), None, (at(1), None, False)),
    (UNSPECIFIED, at(5), (None, at(5), True)),
    (UNSPECIFIED, UNSPECIFIED, (None, None, False)),
])
def test_history_range(start, end, expected):
    assert history_range(start, end) == expected


@pytest.fixture
async def plain_history(storage, registry):
    plain = register(registry, "Plain")
    for minute in range(10):
        await storage.save_node_value(node_id(plain), sample(float(minute), at(minute)))
    await storage.drain()
    return plain


def values(data_values):
    return [dv.Value.Value for dv in data_values]


async def test_zero_values_per_node_means_no_limit(storage, plain_history):
    data_values, cont = await storage.read_node_history(node_id(plain_history), at(0), at(9), 0)

    assert values(data_values) == [float(m) for m in range(10)]
    assert cont is None


async def test_only_start_reads_forward(storage, plain_history):
    data_values, _ = await storage.read_node_history(node_id(plain_history), at(7), UNSPECIFIED, 0)
    assert values(data_values) == [7.0, 8.0, 9.0]


async def test_only_end_reads_backward(storage, plain_history):
    data_values, _ = await storage.read_node_history(node_id(plain_history), UNSPECIFIED, at(2), 0)
    assert values(data_values) == [2.0, 1.0, 0.0]


async def test_start_after_end_reads_backward(storage, plain_history):
    data_values, _ = await storage.read_node_history(node_id(plain_history), at(5), at(3), 0)
    assert values(data_values) == [5.0, 4.0, 3.0]


async def test_no_time_range_returns_nothing(storage, plain_history):
    data_values, _ = await storage.read_node_history(node_id(plain_history), UNSPECIFIED, UNSPECIFIED, 5)
    assert data_values == []


async def test_values_per_node_paginates_with_continuation(storage, plain_history):
    first, cont = await storage.read_node_history(node_id(plain_history), at(0), at(9), 4)
    assert values(first) == [0.0, 1.0, 2.0, 3.0]
    # o asyncua usa o continuation point como novo StartTime
    assert cont == at(4)

    second, cont = await storage.read_node_history(node_id(plain_history), cont, at(9), 4)
    third, cont = await storage.read_node_history(node_id(plain_history), cont, at(9), 4)
    assert values(second) == [4.0, 5.0, 6.0, 7.0]
    assert values(third) == [8.0, 9.0]
    assert cont is None


async def test_reverse_pagination(storage, plain_history):
    first, cont = await storage.read_node_history(node_id(plain_history), at(9), at(0), 6)
    second, cont = await storage.read_node_history(node_id(plain_history), cont, at(0), 6)

    assert values(first) + values(second) == [float(m) for m in range(9, -1, -1)]
    assert cont is None


async def test_unlimited_read_is_paginated_at_server_maximum(storage, plain_history, monkeypatch):
    monkeypatch.setattr(storage_module, "MAX_HISTORY_VALUES", 3)

    data_values, cont = await storage.read_node_history(node_id(plain_history), at(0), at(9), 0)

    assert values(data_values) == [0.0, 1.0, 2.0]
    assert cont == at(3)


async def test_raw_values_keep_their_variant_type(storage, registry):
    counter = register(registry, "Counter")
    await storage.save_node_value(node_id(counter), sample(7, at(1), ua.VariantType.Int32))
    await storage.drain()

    [dv], _ = await storage.read_node_history(node_id(counter), at(0), at(5), 0)

    assert dv.Value.VariantType == ua.VariantType.Int32
    assert dv.Value.Value == 7
    assert dv.SourceTimestamp == at(1)


async def test_virtual_node_reads_level_average(storage, db, registry):
    voltage = register(registry, "Voltage", SAMPLE_POLICY)
    virtual = register(registry, "Voltage", level="1hour", raw_path=voltage.path)
    db.levels[(table_of(voltage), "1hour")] = [
        {"bucket": at(0), "avg_value": 219.5, "max_value": 221.0, "min_value": 218.0,
         "stddev_value": 1.0, "sample_count": 3600},
    ]

    [dv], _ = await storage.read_node_history(node_id(virtual), at(0), at(60), 0)

    assert dv.Value == ua.Variant(219.5, ua.VariantType.Double)
    assert dv.SourceTimestamp == at(0)


async def test_aggregate_node_reads_its_windows(storage, registry, clock):
    energy = register(registry, "Energy", SUM_15MIN)
    for minute, value in [(1, 1.0), (2, 2.0), (16, 10.0)]:
        await storage.save_node_value(node_id(energy), sample(value, at(minute)))
    clock.now = at(31)
    await storage.flush(energy, table_of(energy))

    data_values, _ = await storage.read_node_history(node_id(energy), at(0), at(60), 0)

    assert [(dv.SourceTimestamp, dv.Value.Value) for dv in data_values] == [(at(0), 3.0), (at(15), 10.0)]
    assert data_values[0].Value.VariantType == ua.VariantType.Double


# -----------------------------------------------------------------------------
# HDAManager
# -----------------------------------------------------------------------------

async def test_manager_enables_history_read_on_virtual_nodes(db, registry):
    voltage = register(registry, "Voltage", SAMPLE_POLICY)
    virtual = register(registry, "Voltage", level="1min", raw_path=voltage.path)
    server = SimpleNamespace(
        set_history_storage=AsyncMock(),
        historize_node=AsyncMock(),
        enable_history_read=AsyncMock(),
    )

    manager = HDAManager(server=server, db=db, registry=registry)
    await manager.init([voltage.node])

    server.historize_node.assert_awaited_once_with(voltage.node)
    server.enable_history_read.assert_awaited_once_with(virtual.node)
    assert db.connected

    await manager.stop()
    assert not db.connected

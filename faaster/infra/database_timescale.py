from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from faaster.interfaces.idatabase import IDatabase
from faaster.hda.buffer import WindowResult
from faaster.hda.policies import AggregationPolicy, HDAFunction, LEVEL_REFRESH, WINDOW_SECONDS
from faaster.log import get_logger

import asyncio
import asyncpg
import hashlib
import re


logger = get_logger(__name__)

# compressão da hypertable raw (modo sample)
_COMPRESS_AFTER = "7 days"

# sufixo da hypertable do modo aggregate — convive com a raw do mesmo nó,
# então trocar de modo no modelo não apaga o histórico do outro modo
_AGGREGATE_SUFFIX = "_agg"

_RELATION_NAME = re.compile(r"^[0-9a-z_]+$")

# continuous aggregate de um level, sempre calculado direto da hypertable raw.
# materialized_only = false: a consulta completa em tempo real os buckets
# ainda não materializados pela policy de atualização.
_AGGREGATE_VIEW_SQL = """
    CREATE MATERIALIZED VIEW "{view}"
    WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
    SELECT
        time_bucket(INTERVAL '{bucket}', source_timestamp) AS bucket,
        AVG(value)                                        AS avg_value,
        MAX(value)                                        AS max_value,
        MIN(value)                                        AS min_value,
        STDDEV(value)                                     AS stddev_value,
        COUNT(value)                                      AS sample_count
    FROM "{table}"
    GROUP BY 1
    WITH NO DATA
"""

# como combinar um agregado com o já gravado na mesma janela (amostras atrasadas)
_MERGE_VALUE: Dict[HDAFunction, str] = {
    HDAFunction.mean: (
        "(current.value * current.sample_count + EXCLUDED.value * EXCLUDED.sample_count)"
        " / (current.sample_count + EXCLUDED.sample_count)"
    ),
    HDAFunction.sum: "current.value + EXCLUDED.value",
    HDAFunction.max: "GREATEST(current.value, EXCLUDED.value)",
    HDAFunction.min: "LEAST(current.value, EXCLUDED.value)",
    HDAFunction.last: (
        "CASE WHEN EXCLUDED.last_timestamp >= current.last_timestamp"
        " THEN EXCLUDED.value ELSE current.value END"
    ),
}


def build_index(submodel_id: str, path: str) -> str:
    return f"{submodel_id}::{path}"


def build_table_name(index: str) -> str:
    return hashlib.md5(index.encode()).hexdigest()


def aggregate_table_name(table_name: str) -> str:
    return f"{table_name}{_AGGREGATE_SUFFIX}"


def view_name(table_name: str, level: str) -> str:
    return f"{table_name}_{level}"


def view_definition(level: str) -> str:
    """
    Impressão digital da definição da view de um level: muda quando o bucket
    ou o SQL da view mudam, e então a view é recriada na próxima partida.
    """
    sql = _AGGREGATE_VIEW_SQL.format(view="", table="", bucket=_bucket_interval(level))
    return hashlib.sha1(" ".join(sql.split()).encode()).hexdigest()


def _bucket_interval(level: str) -> str:
    return f"{WINDOW_SECONDS[level]} seconds"


def _relation(name: str) -> str:
    """Literal regclass de uma tabela/view do Faaster (nomes gerados, nunca do usuário)."""
    if not _RELATION_NAME.match(name):
        raise ValueError(f"invalid relation name: {name!r}")
    return f"'\"{name}\"'"


def _retention_text(policy: Optional[AggregationPolicy]) -> Optional[str]:
    if policy is None:
        return None
    if policy.is_aggregate:
        return policy.retention_aggregate
    return ",".join(f"{level}={kept or 'none'}" for level, kept in policy.retention.items())


class TimescaleDatabase(IDatabase):

    def __init__(self, url: str, db_name: str) -> None:
        self._url = url
        self._db_name = db_name
        self._pool: Optional[asyncpg.Pool] = None
        self._backfills: Set[asyncio.Task] = set()

    async def connect(self) -> None:
        await self._ensure_database_exists()
        self._pool = await asyncpg.create_pool(
            dsn=f"{self._url}/{self._db_name}",
            min_size=2,
            max_size=10,
        )
        await self.bootstrap()
        logger.info("timescale.connected", db=self._db_name)

    async def _ensure_database_exists(self) -> None:
        """
        Conecta na database padrão 'postgres' e cria
        a database do AAS se não existir.

        CREATE DATABASE não pode rodar dentro de uma transação
        no PostgreSQL — por isso usamos uma conexão direta
        com autocommit em vez do pool.
        """
        conn = await asyncpg.connect(
            dsn=f"{self._url}/postgres"
        )
        try:
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                self._db_name,
            )
            if not exists:
                # CREATE DATABASE não suporta parâmetros — sanitizamos o nome
                safe_name = self._db_name.replace('"', '')
                await conn.execute(f'CREATE DATABASE "{safe_name}"')
                logger.info(
                    "timescale.database.created",
                    db=self._db_name,
                )
            else:
                logger.info(
                    "timescale.database.exists",
                    db=self._db_name,
                )
        finally:
            await conn.close()

    async def disconnect(self) -> None:
        # backfills interrompidos são retomados na próxima partida
        for task in list(self._backfills):
            task.cancel()
        if self._backfills:
            await asyncio.gather(*self._backfills, return_exceptions=True)

        if self._pool:
            await self._pool.close()
        logger.info("timescale.disconnected")

    async def bootstrap(self) -> None:
        """Cria as tabelas de metadados faaster_nodes e faaster_aggregates."""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE EXTENSION IF NOT EXISTS timescaledb;

                CREATE TABLE IF NOT EXISTS faaster_nodes (
                    table_name   VARCHAR(32)  PRIMARY KEY,
                    index_path   TEXT         NOT NULL,
                    id_short     TEXT         NOT NULL,
                    submodel     TEXT         NOT NULL,
                    submodel_id  TEXT         NOT NULL,
                    path         TEXT         NOT NULL,
                    semantic_id  TEXT,
                    hda_mode     TEXT,
                    hda_window   TEXT,
                    hda_function TEXT,
                    hda_levels   TEXT,
                    created_at   TIMESTAMPTZ  DEFAULT NOW()
                );
                ALTER TABLE faaster_nodes ADD COLUMN IF NOT EXISTS hda_retention TEXT;
                ALTER TABLE faaster_nodes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

                CREATE TABLE IF NOT EXISTS faaster_aggregates (
                    view_name      TEXT         PRIMARY KEY,
                    table_name     TEXT         NOT NULL,
                    level          TEXT         NOT NULL,
                    definition     TEXT         NOT NULL,
                    created_at     TIMESTAMPTZ  DEFAULT NOW(),
                    backfilled_at  TIMESTAMPTZ
                );
            """)
        logger.info("timescale.bootstrap.done")

    async def create_node_table(
        self,
        table_name: str,
        index: str,
        id_short: str,
        submodel: str,
        submodel_id: str,
        path: str,
        semantic_id: Optional[str],
        policy: Optional[AggregationPolicy],
    ) -> None:
        async with self._pool.acquire() as conn:
            await self._register_metadata(
                conn=conn,
                table_name=table_name,
                index=index,
                id_short=id_short,
                submodel=submodel,
                submodel_id=submodel_id,
                path=path,
                semantic_id=semantic_id,
                policy=policy,
            )

            if policy is None:
                # sem policy — hypertable raw simples, sem expiração
                await self._create_raw_hypertable(conn, table_name)
                await self._set_retention(conn, table_name, None)
                logger.info(
                    "timescale.node_table.ready.no_policy",
                    table_name=table_name,
                    path=path,
                )

            elif policy.is_sample:
                await self._create_raw_hypertable(conn, table_name)
                await self._apply_compression(conn, table_name)
                await self._set_retention(conn, table_name, policy.retention.get("raw"))
                await self._sync_continuous_aggregates(conn, table_name, policy)
                logger.info(
                    "timescale.node_table.ready.sample",
                    table_name=table_name,
                    path=path,
                    levels=policy.levels,
                )

            elif policy.is_aggregate:
                aggregate_table = aggregate_table_name(table_name)
                await self._create_aggregate_hypertable(conn, aggregate_table)
                await self._set_retention(conn, aggregate_table, policy.retention_aggregate)
                logger.info(
                    "timescale.node_table.ready.aggregate",
                    table_name=aggregate_table,
                    path=path,
                    window=policy.window,
                    function=policy.function.value,
                )

    async def _register_metadata(
        self,
        conn: asyncpg.Connection,
        table_name: str,
        index: str,
        id_short: str,
        submodel: str,
        submodel_id: str,
        path: str,
        semantic_id: Optional[str],
        policy: Optional[AggregationPolicy],
    ) -> None:
        await conn.execute("""
            INSERT INTO faaster_nodes (
                table_name, index_path, id_short, submodel,
                submodel_id, path, semantic_id,
                hda_mode, hda_window, hda_function, hda_levels, hda_retention
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            ON CONFLICT (table_name) DO UPDATE SET
                id_short      = EXCLUDED.id_short,
                submodel      = EXCLUDED.submodel,
                semantic_id   = EXCLUDED.semantic_id,
                hda_mode      = EXCLUDED.hda_mode,
                hda_window    = EXCLUDED.hda_window,
                hda_function  = EXCLUDED.hda_function,
                hda_levels    = EXCLUDED.hda_levels,
                hda_retention = EXCLUDED.hda_retention,
                updated_at    = NOW()
        """,
            table_name, index, id_short, submodel,
            submodel_id, path, semantic_id,
            policy.mode.value if policy else None,
            policy.window if policy else None,
            policy.function.value if policy and policy.is_aggregate else None,
            ",".join(policy.levels) if policy and policy.is_sample else None,
            _retention_text(policy),
        )

    async def _create_raw_hypertable(
        self,
        conn: asyncpg.Connection,
        table_name: str,
    ) -> None:
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                source_timestamp  TIMESTAMPTZ      NOT NULL,
                value             DOUBLE PRECISION,
                variant_type      SMALLINT         NOT NULL
            );
        """)
        await conn.execute(f"""
            SELECT create_hypertable(
                {_relation(table_name)},
                'source_timestamp',
                if_not_exists => TRUE
            );
        """)

    async def _create_aggregate_hypertable(
        self,
        conn: asyncpg.Connection,
        table_name: str,
    ) -> None:
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                bucket                TIMESTAMPTZ      NOT NULL,
                aggregation_window    TEXT             NOT NULL,
                aggregation_function  TEXT             NOT NULL,
                value                 DOUBLE PRECISION NOT NULL,
                sample_count          INTEGER          NOT NULL,
                last_timestamp        TIMESTAMPTZ      NOT NULL,
                UNIQUE (bucket, aggregation_window, aggregation_function)
            );
        """)
        await conn.execute(f"""
            SELECT create_hypertable(
                {_relation(table_name)},
                'bucket',
                if_not_exists => TRUE
            );
        """)

    async def _apply_compression(
        self,
        conn: asyncpg.Connection,
        table_name: str,
    ) -> None:
        # reconfigurar a compressão falha se já houver chunks comprimidos
        enabled = await conn.fetchval("""
            SELECT compression_enabled
            FROM timescaledb_information.hypertables
            WHERE hypertable_name = $1
        """, table_name)

        if not enabled:
            await conn.execute(f"""
                ALTER TABLE "{table_name}" SET (
                    timescaledb.compress,
                    timescaledb.compress_orderby = 'source_timestamp DESC'
                );
            """)

        await conn.execute(f"""
            SELECT add_compression_policy(
                {_relation(table_name)},
                INTERVAL '{_COMPRESS_AFTER}',
                if_not_exists => TRUE
            );
        """)

    async def _set_retention(
        self,
        conn: asyncpg.Connection,
        relation: str,
        retention: Optional[str],
    ) -> None:
        """Recria a retention policy conforme o modelo (None → sem expiração)."""
        await conn.execute(f"""
            SELECT remove_retention_policy({_relation(relation)}, if_exists => TRUE);
        """)
        if retention is not None:
            await conn.execute(f"""
                SELECT add_retention_policy(
                    {_relation(relation)},
                    drop_after => $1::text::interval
                );
            """, retention)

    async def _sync_continuous_aggregates(
        self,
        conn: asyncpg.Connection,
        table_name: str,
        policy: AggregationPolicy,
    ) -> None:
        """
        Reconcilia as views de levels com a policy do modelo:

            level novo ou definição alterada → (re)cria a view e reprocessa o
                                               histórico raw em segundo plano
            level inalterado                 → mantém a view e seus dados
            level removido do modelo         → apaga a view
            policies (atualização/retenção)  → sempre recriadas, custo desprezível

        Agregados mais antigos que a retenção raw não podem ser recalculados:
        por isso uma view só é recriada quando sua definição muda de fato.
        """
        desired = {view_name(table_name, level): level for level in policy.levels}

        existing = {
            row["view_name"] for row in await conn.fetch("""
                SELECT view_name
                FROM timescaledb_information.continuous_aggregates
                WHERE view_name LIKE $1
            """, f"{table_name}\\_%")
        }
        recorded = {
            row["view_name"]: row for row in await conn.fetch("""
                SELECT view_name, definition, backfilled_at
                FROM faaster_aggregates
                WHERE table_name = $1
            """, table_name)
        }

        for view in sorted((existing | set(recorded)) - set(desired)):
            await self._drop_view(conn, view)
            logger.warning("timescale.continuous_aggregate.dropped", view_name=view, reason="level removed")

        for view, level in desired.items():
            definition = view_definition(level)
            row = recorded.get(view)

            if view in existing and row is not None and row["definition"] == definition:
                if row["backfilled_at"] is None:
                    self._schedule_backfill(view)
            else:
                if view in existing:
                    await self._drop_view(conn, view)
                    logger.warning(
                        "timescale.continuous_aggregate.dropped",
                        view_name=view,
                        reason="definition changed",
                    )
                await self._create_view(conn, table_name, view, level, definition)
                self._schedule_backfill(view)

            refresh = LEVEL_REFRESH[level]
            await conn.execute(f"""
                SELECT remove_continuous_aggregate_policy({_relation(view)}, if_exists => TRUE);
            """)
            await conn.execute(f"""
                SELECT add_continuous_aggregate_policy(
                    {_relation(view)},
                    start_offset      => $1::interval,
                    end_offset        => $2::interval,
                    schedule_interval => $3::interval
                );
            """, refresh.start_offset, refresh.end_offset, refresh.schedule_interval)

            await self._set_retention(conn, view, policy.retention.get(level))

    async def _create_view(
        self,
        conn: asyncpg.Connection,
        table_name: str,
        view: str,
        level: str,
        definition: str,
    ) -> None:
        await conn.execute(_AGGREGATE_VIEW_SQL.format(
            view=view,
            table=table_name,
            bucket=_bucket_interval(level),
        ))
        await conn.execute("""
            INSERT INTO faaster_aggregates (view_name, table_name, level, definition)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (view_name) DO UPDATE SET
                level         = EXCLUDED.level,
                definition    = EXCLUDED.definition,
                created_at    = NOW(),
                backfilled_at = NULL
        """, view, table_name, level, definition)
        logger.info("timescale.continuous_aggregate.created", view_name=view, level=level)

    async def _drop_view(self, conn: asyncpg.Connection, view: str) -> None:
        await conn.execute(f'DROP MATERIALIZED VIEW IF EXISTS "{view}" CASCADE;')
        await conn.execute("DELETE FROM faaster_aggregates WHERE view_name = $1", view)

    def _schedule_backfill(self, view: str) -> None:
        task = asyncio.create_task(self._backfill(view), name=f"faaster.hda.backfill.{view}")
        self._backfills.add(task)
        task.add_done_callback(self._backfills.discard)

    async def _backfill(self, view: str) -> None:
        """
        Materializa todo o histórico raw existente numa view nova ou recriada.
        Custo proporcional aos dados raw retidos; roda em segundo plano porque a
        consulta já é correta antes disso (agregação em tempo real).
        """
        try:
            async with self._pool.acquire() as conn:
                # refresh_continuous_aggregate não roda dentro de transação
                await conn.execute(f"CALL refresh_continuous_aggregate({_relation(view)}, NULL, NULL);")
                await conn.execute(
                    "UPDATE faaster_aggregates SET backfilled_at = NOW() WHERE view_name = $1", view
                )
            logger.info("timescale.continuous_aggregate.backfilled", view_name=view)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("timescale.continuous_aggregate.backfill_failed", view_name=view, error=str(exc))

    async def wait_backfills(self) -> None:
        """Aguarda os backfills em andamento (testes e ferramentas)."""
        while self._backfills:
            await asyncio.gather(*list(self._backfills), return_exceptions=True)

    async def insert(
        self,
        table_name: str,
        value: Any,
        source_timestamp: datetime,
        variant_type: int,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO "{table_name}"
                    (source_timestamp, value, variant_type)
                VALUES ($1, $2, $3)
            """, source_timestamp, float(value), variant_type)

    async def insert_aggregate(
        self,
        table_name: str,
        result: WindowResult,
        window: str,
        function: HDAFunction,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO "{aggregate_table_name(table_name)}" AS current
                    (bucket, aggregation_window, aggregation_function,
                     value, sample_count, last_timestamp)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (bucket, aggregation_window, aggregation_function) DO UPDATE SET
                    value          = {_MERGE_VALUE[function]},
                    sample_count   = current.sample_count + EXCLUDED.sample_count,
                    last_timestamp = GREATEST(current.last_timestamp, EXCLUDED.last_timestamp)
            """,
                result.bucket, window, function.value,
                result.value, result.sample_count, result.last_timestamp,
            )

    async def query(
        self,
        table_name: str,
        start: Optional[datetime],
        end: Optional[datetime],
        limit: int,
        level: str = "raw",
        reverse: bool = False,
    ) -> List[Dict]:
        if level == "raw":
            target = table_name
            time_col = "source_timestamp"
            cols = "source_timestamp, value, variant_type"
        else:
            target = view_name(table_name, level)
            time_col = "bucket"
            cols = (
                "bucket, avg_value, max_value, "
                "min_value, stddev_value, sample_count"
            )

        return await self._fetch_range(target, cols, time_col, start, end, limit, reverse)

    async def query_aggregate(
        self,
        table_name: str,
        start: Optional[datetime],
        end: Optional[datetime],
        limit: int,
        window: str,
        function: HDAFunction,
        reverse: bool = False,
    ) -> List[Dict]:
        return await self._fetch_range(
            aggregate_table_name(table_name),
            "bucket, value, sample_count, last_timestamp",
            "bucket",
            start,
            end,
            limit,
            reverse,
            filters={"aggregation_window": window, "aggregation_function": function.value},
        )

    async def _fetch_range(
        self,
        target: str,
        cols: str,
        time_col: str,
        start: Optional[datetime],
        end: Optional[datetime],
        limit: int,
        reverse: bool,
        filters: Optional[Dict[str, str]] = None,
    ) -> List[Dict]:
        """Linhas com start <= tempo <= end (limites opcionais), em ordem crescente ou reversa."""
        conditions: List[str] = []
        params: List[Any] = []

        for column, value in (filters or {}).items():
            params.append(value)
            conditions.append(f"{column} = ${len(params)}")
        if start is not None:
            params.append(start)
            conditions.append(f"{time_col} >= ${len(params)}")
        if end is not None:
            params.append(end)
            conditions.append(f"{time_col} <= ${len(params)}")
        params.append(limit)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        order = "DESC" if reverse else "ASC"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT {cols}
                FROM "{target}"
                {where}
                ORDER BY {time_col} {order}
                LIMIT ${len(params)}
            """, *params)

        return [dict(row) for row in rows]

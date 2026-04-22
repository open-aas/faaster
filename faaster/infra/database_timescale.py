from datetime import datetime
from typing import Any, Dict, List, Optional

from faaster.interfaces.idatabase import IDatabase
from faaster.hda.policies import AggregationPolicy, HDAMode
from faaster.log import get_logger

import asyncpg
import hashlib


logger = get_logger(__name__)

# mapeamento fixo de strings de retenção para INTERVAL SQL
_RETENTION_INTERVAL: Dict[str, Optional[str]] = {
    "7 days":   "INTERVAL '7 days'",
    "30 days":  "INTERVAL '30 days'",
    "90 days":  "INTERVAL '90 days'",
    "180 days": "INTERVAL '180 days'",
    "1 year":   "INTERVAL '1 year'",
    "2 years":  "INTERVAL '2 years'",
    "3 years":  "INTERVAL '3 years'",
    "5 years":  "INTERVAL '5 years'",
    "10 years": "INTERVAL '10 years'",
    None:       None,
}

# configuração de cada level:
# (bucket_interval, start_offset, end_offset, schedule_interval)
_LEVEL_CONFIG: Dict[str, tuple] = {
    "1min":  ("1 minute",  "10 minutes", "1 minute",  "1 minute"),
    "5min":  ("5 minutes", "30 minutes", "5 minutes", "5 minutes"),
    "10min": ("10 minutes","1 hour",     "10 minutes","10 minutes"),
    "15min": ("15 minutes","1 hour",     "15 minutes","15 minutes"),
    "1hour": ("1 hour",    "2 hours",    "1 hour",    "1 hour"),
    "1day":  ("1 day",     "2 days",     "1 day",     "1 day"),
}


def build_index(submodel_id: str, path: str) -> str:
    return f"{submodel_id}::{path}"


def build_table_name(index: str) -> str:
    return hashlib.md5(index.encode()).hexdigest()


def _get_retention_interval(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    interval = _RETENTION_INTERVAL.get(value)
    if interval is None and value is not None:
        logger.warning(
            "timescale.unknown_retention",
            value=value,
            hint=f"Supported: {list(_RETENTION_INTERVAL.keys())}",
        )
    return interval


class TimescaleDatabase(IDatabase):

    def __init__(self, url: str, db_name: str) -> None:
        self._url = url
        self._db_name = db_name
        self._pool: Optional[asyncpg.Pool] = None

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
        if self._pool:
            await self._pool.close()
        logger.info("timescale.disconnected")

    async def bootstrap(self) -> None:
        """Cria a tabela de metadados faaster_nodes."""
        async with self._pool.acquire() as conn:
            await conn.execute("""
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
                # sem policy — hypertable raw simples
                await self._create_raw_hypertable(conn, table_name)
                logger.info(
                    "timescale.node_table.created.no_policy",
                    table_name=table_name,
                    path=path,
                )

            elif policy.is_sample:
                await self._create_raw_hypertable(conn, table_name)
                await self._apply_compression(conn, table_name)
                await self._apply_raw_retention(conn, table_name, policy)
                await self._create_continuous_aggregates(conn, table_name, policy)
                logger.info(
                    "timescale.node_table.created.sample",
                    table_name=table_name,
                    path=path,
                    levels=policy.levels,
                )

            elif policy.is_aggregate:
                await self._create_aggregate_hypertable(conn, table_name)
                await self._apply_aggregate_retention(conn, table_name, policy)
                logger.info(
                    "timescale.node_table.created.aggregate",
                    table_name=table_name,
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
                hda_mode, hda_window, hda_function, hda_levels
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            ON CONFLICT (table_name) DO NOTHING
        """,
            table_name, index, id_short, submodel,
            submodel_id, path, semantic_id,
            policy.mode.value if policy else None,
            policy.window if policy else None,
            policy.function.value if policy and policy.is_aggregate else None,
            ",".join(policy.levels) if policy and policy.is_sample else None,
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
                '{table_name}',
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
                bucket        TIMESTAMPTZ      NOT NULL,
                value         DOUBLE PRECISION,
                sample_count  INTEGER,
                window        TEXT             NOT NULL,
                function      TEXT             NOT NULL
            );
        """)
        await conn.execute(f"""
            SELECT create_hypertable(
                '{table_name}',
                'bucket',
                if_not_exists => TRUE
            );
        """)

    async def _apply_compression(
        self,
        conn: asyncpg.Connection,
        table_name: str,
    ) -> None:
        await conn.execute(f"""
            ALTER TABLE "{table_name}" SET (
                timescaledb.compress,
                timescaledb.compress_orderby = 'source_timestamp DESC'
            );
        """)
        await conn.execute(f"""
            SELECT add_compression_policy(
                '{table_name}',
                INTERVAL '7 days',
                if_not_exists => TRUE
            );
        """)

    async def _apply_raw_retention(
        self,
        conn: asyncpg.Connection,
        table_name: str,
        policy: AggregationPolicy,
    ) -> None:
        raw_retention = policy.retention.get("raw")
        interval = _get_retention_interval(raw_retention)
        if interval:
            await conn.execute(f"""
                SELECT add_retention_policy(
                    '{table_name}',
                    {interval},
                    if_not_exists => TRUE
                );
            """)

    async def _apply_aggregate_retention(
        self,
        conn: asyncpg.Connection,
        table_name: str,
        policy: AggregationPolicy,
    ) -> None:
        interval = _get_retention_interval(policy.retention_aggregate)
        if interval:
            await conn.execute(f"""
                SELECT add_retention_policy(
                    '{table_name}',
                    {interval},
                    if_not_exists => TRUE
                );
            """)

    async def _create_continuous_aggregates(
        self,
        conn: asyncpg.Connection,
        table_name: str,
        policy: AggregationPolicy,
    ) -> None:
        for i, level in enumerate(policy.levels):
            if level not in _LEVEL_CONFIG:
                logger.warning(
                    "timescale.unknown_level",
                    level=level,
                    table_name=table_name,
                )
                continue

            await self._create_one_aggregate(
                conn=conn,
                table_name=table_name,
                level=level,
                level_index=i,
                policy=policy,
            )

    async def _create_one_aggregate(
        self,
        conn: asyncpg.Connection,
        table_name: str,
        level: str,
        level_index: int,
        policy: AggregationPolicy,
    ) -> None:
        bucket, start_offset, end_offset, schedule = _LEVEL_CONFIG[level]
        view_name = f"{table_name}_{level}"

        # agrega sobre o level anterior se possível
        if level_index == 0:
            source = f'"{table_name}"'
            value_col = "value"
            time_col = "source_timestamp"
        else:
            prev_level = policy.levels[level_index - 1]
            source = f'"{table_name}_{prev_level}"'
            value_col = "avg_value"
            time_col = "bucket"

        await conn.execute(f"""
            CREATE MATERIALIZED VIEW IF NOT EXISTS "{view_name}"
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('{bucket}', {time_col})   AS bucket,
                AVG({value_col})                       AS avg_value,
                MAX({value_col})                       AS max_value,
                MIN({value_col})                       AS min_value,
                STDDEV({value_col})                    AS stddev_value,
                COUNT(*)                               AS sample_count
            FROM {source}
            GROUP BY bucket
            WITH NO DATA;
        """)

        await conn.execute(f"""
            SELECT add_continuous_aggregate_policy(
                '{view_name}',
                start_offset  => INTERVAL '{start_offset}',
                end_offset    => INTERVAL '{end_offset}',
                schedule_interval => INTERVAL '{schedule}',
                if_not_exists => TRUE
            );
        """)

        # retenção do level
        level_retention = policy.retention.get(level)
        interval = _get_retention_interval(level_retention)
        if interval:
            await conn.execute(f"""
                SELECT add_retention_policy(
                    '{view_name}',
                    {interval},
                    if_not_exists => TRUE
                );
            """)

        logger.info(
            "timescale.continuous_aggregate.created",
            view_name=view_name,
            level=level,
            source=source,
        )

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
        bucket: datetime,
        value: float,
        sample_count: int,
        window: str,
        function: str,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO "{table_name}"
                    (bucket, value, sample_count, window, function)
                VALUES ($1, $2, $3, $4, $5)
            """, bucket, value, sample_count, window, function)

    async def query(
        self,
        table_name: str,
        start: datetime,
        end: datetime,
        limit: int,
        level: str = "raw",
    ) -> List[Dict]:
        if level == "raw":
            target = f'"{table_name}"'
            time_col = "source_timestamp"
            cols = "source_timestamp, value, variant_type"
        else:
            target = f'"{table_name}_{level}"'
            time_col = "bucket"
            cols = (
                "bucket, avg_value, max_value, "
                "min_value, stddev_value, sample_count"
            )

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT {cols}
                FROM {target}
                WHERE {time_col} BETWEEN $1 AND $2
                ORDER BY {time_col} ASC
                LIMIT $3
            """, start, end, limit)

        return [dict(row) for row in rows]

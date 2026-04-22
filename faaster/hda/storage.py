from datetime import datetime, timezone
from typing import List
from asyncua.ua import NodeId, DataValue, Variant, VariantType
from faaster.parser.node_registry import NodeRegistry, NodeMetadata
from faaster.interfaces.idatabase import IDatabase
from .policies import HDAMode, HDAFunction
from faaster.infra.database_timescale import build_index, build_table_name
from faaster.interfaces.ihda import IHDAStorage
from faaster.log import get_logger

import asyncio
import statistics


logger = get_logger(__name__)


class TimescaleHDAStorage(IHDAStorage):

    def __init__(
        self,
        db: IDatabase,
        registry: NodeRegistry,
    ) -> None:
        self._db = db
        self._registry = registry
        super().__init__()

    async def init(self) -> None:
        await self._db.connect()

    async def new_historized_node(
        self,
        node_id: NodeId,
        period,
        count: int = 0,
    ) -> None:
        """
        Chamado pelo asyncua quando um nó é registrado para HDA.
        Cria a hypertable e inicia o timer se modo aggregate.
        """
        node_id_str = str(node_id)
        metadata = self._registry.get_by_node_id(node_id_str)

        if metadata is None:
            logger.warning(
                "hda.new_historized_node.not_found",
                node_id=node_id_str,
            )
            return

        # nós virtuais (Value@1min etc) não criam tabelas próprias
        # — consultam a tabela do nó raw com sufixo de level
        if metadata.is_virtual:
            logger.info(
                "hda.new_historized_node.virtual.skipped",
                node_id=node_id_str,
                path=metadata.path,
                level=metadata.level,
            )
            return

        index = build_index(metadata.submodel_id, metadata.path)
        table_name = build_table_name(index)

        await self._db.create_node_table(
            table_name=table_name,
            index=index,
            id_short=metadata.id_short,
            submodel=metadata.submodel,
            submodel_id=metadata.submodel_id,
            path=metadata.path,
            semantic_id=metadata.semantic_id,
            policy=metadata.aggregation_policy,
        )

        # inicia timer da janela se modo aggregate
        if (
            metadata.aggregation_policy is not None
            and metadata.aggregation_policy.is_aggregate
        ):
            task = asyncio.create_task(
                self._aggregate_window_loop(metadata, table_name),
                name=f"faaster.hda.aggregate.{metadata.id_short}",
            )
            metadata.buffer.task = task

        logger.info(
            "hda.new_historized_node.done",
            node_id=node_id_str,
            path=metadata.path,
            table_name=table_name,
            mode=metadata.aggregation_policy.mode.value
            if metadata.aggregation_policy else "none",
        )

    async def save_node_value(
        self,
        node_id: NodeId,
        data_value: DataValue,
    ) -> None:
        """
        Chamado pelo asyncua quando um nó historizado é atualizado.

        nó virtual   → ignora — dados vêm do nó raw
        modo sample  → insere diretamente na hypertable
        modo aggregate → acumula no buffer
        sem policy   → insere diretamente na hypertable raw
        """
        node_id_str = str(node_id)
        metadata = self._registry.get_by_node_id(node_id_str)

        if metadata is None:
            return

        # nós virtuais não persistem — só consultam
        if metadata.is_virtual:
            return

        value = data_value.Value.Value
        timestamp = data_value.SourceTimestamp or datetime.now(tz=timezone.utc)
        variant_type = data_value.Value.VariantType.value

        index = build_index(metadata.submodel_id, metadata.path)
        table_name = build_table_name(index)

        policy = metadata.aggregation_policy

        # sem policy ou modo sample → insere direto
        if policy is None or policy.is_sample:
            await self._db.insert(
                table_name=table_name,
                value=value,
                source_timestamp=timestamp,
                variant_type=variant_type,
            )
            logger.info(
                "hda.save_node_value.inserted",
                path=metadata.path,
                value=value,
                mode=policy.mode.value if policy else "none",
            )

        # modo aggregate → acumula no buffer
        elif policy.is_aggregate:
            metadata.buffer.push(float(value), timestamp)
            logger.info(
                "hda.save_node_value.buffered",
                path=metadata.path,
                value=value,
                buffer_size=len(metadata.buffer.values),
            )

    async def read_node_history(
        self,
        node_id: NodeId,
        start: datetime,
        end: datetime,
        nb_values: int,
    ):
        """
        Chamado pelo asyncua quando um cliente solicita histórico.

        nó raw     → consulta tabela raw
        nó virtual → consulta tabela do raw com sufixo do level
                     ex: Value@1hour → "{md5}_1hour"
        """
        node_id_str = str(node_id)
        metadata = self._registry.get_by_node_id(node_id_str)

        if metadata is None:
            return [], None

        # resolve a tabela base sempre a partir do nó raw
        # nós virtuais compartilham a mesma tabela base
        raw_path = metadata.path.split("@")[0] if metadata.is_virtual else metadata.path
        raw_metadata = self._registry.get_by_path(raw_path)

        if raw_metadata is None:
            logger.warning(
                "hda.read_node_history.raw_not_found",
                path=raw_path,
            )
            return [], None

        index = build_index(raw_metadata.submodel_id, raw_metadata.path)
        table_name = build_table_name(index)

        # level vem direto do metadata — sem resolve_level
        level = metadata.level

        logger.info(
            "hda.read_node_history",
            path=metadata.path,
            level=level,
            table_name=f"{table_name}{metadata.table_suffix}",
            start=str(start),
            end=str(end),
        )

        rows = await self._db.query(
            table_name=table_name,
            start=start,
            end=end,
            limit=nb_values,
            level=level,
        )

        data_values = [_row_to_data_value(row, level) for row in rows]

        continuation = None
        if len(data_values) == nb_values and data_values:
            continuation = data_values[-1].SourceTimestamp

        return data_values, continuation

    async def _aggregate_window_loop(
        self,
        metadata: NodeMetadata,
        table_name: str,
    ) -> None:
        policy = metadata.aggregation_policy
        window_seconds = policy.window_seconds

        if window_seconds is None:
            logger.error(
                "hda.aggregate_window.invalid",
                id_short=metadata.id_short,
                window=policy.window,
            )
            return

        logger.info(
            "hda.aggregate_window.started",
            id_short=metadata.id_short,
            window=policy.window,
            window_seconds=window_seconds,
        )

        while True:
            await asyncio.sleep(window_seconds)
            await self._flush_buffer(metadata, table_name)

    async def _flush_buffer(
        self,
        metadata: NodeMetadata,
        table_name: str,
    ) -> None:
        policy = metadata.aggregation_policy
        values = metadata.buffer.flush()

        if not values:
            logger.info(
                "hda.flush_buffer.empty",
                id_short=metadata.id_short,
            )
            return

        bucket = metadata.buffer.window_start or datetime.now(tz=timezone.utc)
        result = _compute_aggregate(values, policy.function)

        await self._db.insert_aggregate(
            table_name=table_name,
            bucket=bucket,
            value=result,
            sample_count=len(values),
            window=policy.window,
            function=policy.function.value,
        )

        logger.info(
            "hda.flush_buffer.done",
            id_short=metadata.id_short,
            bucket=str(bucket),
            value=result,
            sample_count=len(values),
            function=policy.function.value,
        )

        metadata.buffer.clear()

    async def new_historized_event(self, source_id, evtypes, period, count=0):
        pass

    async def save_event(self, event):
        pass

    async def read_event_history(self, source_id, start, end, nb_values, evfilter):
        pass

    async def stop(self) -> None:
        await self._db.disconnect()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _compute_aggregate(
    values: List[float],
    function: HDAFunction,
) -> float:
    if function == HDAFunction.mean:
        return statistics.mean(values)
    if function == HDAFunction.sum:
        return sum(values)
    if function == HDAFunction.max:
        return max(values)
    if function == HDAFunction.min:
        return min(values)
    if function == HDAFunction.last:
        return values[-1]
    return statistics.mean(values)

def _row_to_data_value(row: dict, level: str) -> DataValue:
    if level == "raw":
        val = row["value"]
        vtype =VariantType(row["variant_type"])

        if isinstance(val, float):
            vtype = VariantType.Double

        dv = DataValue(
            Value=Variant(Value=val, VariantType=vtype),
            SourceTimestamp=row["source_timestamp"],
        )
    else:
        dv = DataValue(
            Value=Variant(Value=row["avg_value"], VariantType=VariantType.Double),
            SourceTimestamp=row["bucket"],
        )
    return dv

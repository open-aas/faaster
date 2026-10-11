from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional, Set, Tuple
from asyncua.ua import NodeId, DataValue, Variant, VariantType
from faaster.parser.node_registry import NodeRegistry, NodeMetadata
from faaster.interfaces.idatabase import IDatabase
from .buffer import bucket_start
from faaster.infra.database_timescale import build_index, build_table_name
from faaster.interfaces.ihda import IHDAStorage
from faaster.log import get_logger

import asyncio


logger = get_logger(__name__)


_NUMERIC_VARIANT_TYPES = {
    VariantType.Boolean,
    VariantType.Int16,
    VariantType.UInt16,
    VariantType.Int32,
    VariantType.UInt32,
    VariantType.Int64,
    VariantType.UInt64,
    VariantType.Float,
    VariantType.Double,
}

# máximo de valores por resposta de HistoryRead; acima disso o cliente
# recebe um continuation point (também quando pede "sem limite", 0)
MAX_HISTORY_VALUES = 10_000

# o OPC UA codifica "não especificado" como DateTime 0 (1601-01-01)
_UNSPECIFIED_UNTIL = datetime(1601, 1, 2, tzinfo=timezone.utc)

# folga após o fim da janela para amostras com timestamp do dispositivo ainda a caminho
_FLUSH_GRACE_SECONDS = 2.0

# tempo máximo para gravar as amostras na fila ao encerrar
_DRAIN_TIMEOUT_SECONDS = 10.0


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _specified(timestamp: Optional[datetime]) -> Optional[datetime]:
    if timestamp is None:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return None if timestamp < _UNSPECIFIED_UNTIL else timestamp


def history_range(
    start: Optional[datetime],
    end: Optional[datetime],
) -> Tuple[Optional[datetime], Optional[datetime], bool]:
    """
    Converte StartTime/EndTime do HistoryRead (OPC 10000-11 §6.4.3.2) em
    (limite inferior, limite superior, ordem reversa):

        start e end        → entre os dois; reversa se start > end
        só start           → de start em diante
        só end             → de end para trás (ordem reversa)
    """
    start, end = _specified(start), _specified(end)

    if start is not None and end is not None:
        if start > end:
            return end, start, True
        return start, end, False
    if end is not None:
        return None, end, True
    return start, None, False


class TimescaleHDAStorage(IHDAStorage):

    def __init__(
        self,
        db: IDatabase,
        registry: NodeRegistry,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._db = db
        self._registry = registry
        self._clock = clock
        # nós no modo aggregate — table_name → metadata
        self._aggregates: Dict[str, NodeMetadata] = {}
        self._tasks: Set[asyncio.Task] = set()
        # amostras raw a gravar, em ordem — a escrita OPC UA não espera o banco
        self._queue: "asyncio.Queue[Tuple[str, str, float, datetime, int]]" = asyncio.Queue()
        self._writer: Optional[asyncio.Task] = None
        self._stopped = False
        super().__init__()

    async def init(self) -> None:
        await self._db.connect()
        self._ensure_writer()

    def _ensure_writer(self) -> None:
        if self._writer is None or self._writer.done():
            self._writer = asyncio.create_task(self._write_loop(), name="faaster.hda.writer")

    async def _write_loop(self) -> None:
        while True:
            path, table_name, value, timestamp, variant_type = await self._queue.get()
            try:
                await self._db.insert(
                    table_name=table_name,
                    value=value,
                    source_timestamp=timestamp,
                    variant_type=variant_type,
                )
            except Exception as exc:
                logger.error("hda.save_node_value.failed", path=path, error=str(exc))
            finally:
                self._queue.task_done()

    async def drain(self) -> None:
        """Aguarda a gravação das amostras raw já recebidas."""
        await self._queue.join()

    async def new_historized_node(
        self,
        node_id: NodeId,
        period,
        count: int = 0,
    ) -> None:
        """
        Chamado pelo asyncua quando um nó é registrado para HDA.
        Cria (ou reconcilia) a hypertable e inicia o timer se modo aggregate.
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
        # — consultam a view do level do nó raw
        if metadata.is_virtual:
            logger.info(
                "hda.new_historized_node.virtual.skipped",
                node_id=node_id_str,
                path=metadata.path,
                level=metadata.level,
            )
            return

        table_name = _table_name(metadata)

        await self._db.create_node_table(
            table_name=table_name,
            index=build_index(metadata.submodel_id, metadata.path),
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
            self._aggregates[table_name] = metadata
            task = asyncio.create_task(
                self._aggregate_window_loop(metadata, table_name),
                name=f"faaster.hda.aggregate.{metadata.id_short}",
            )
            metadata.buffer.task = task
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

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
        Chamado a cada escrita num nó historizado.

        nó virtual   → ignora — dados vêm do nó raw
        modo sample  → enfileira para a hypertable raw
        modo aggregate → acumula no buffer, na janela do timestamp da amostra
        sem policy   → enfileira para a hypertable raw
        """
        node_id_str = str(node_id)
        metadata = self._registry.get_by_node_id(node_id_str)

        if metadata is None:
            return

        # nós virtuais não persistem — só consultam
        if metadata.is_virtual:
            return

        ua_vtype = data_value.Value.VariantType
        if ua_vtype not in _NUMERIC_VARIANT_TYPES or data_value.Value.Value is None:
            logger.warning(
                "hda.save_node_value.skipped.non_numeric",
                path=metadata.path,
                variant_type=ua_vtype.name,
            )
            return

        value = data_value.Value.Value
        timestamp = data_value.SourceTimestamp or data_value.ServerTimestamp or self._clock()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        table_name = _table_name(metadata)
        policy = metadata.aggregation_policy

        # sem policy ou modo sample → grava na raw, pelo worker
        if policy is None or policy.is_sample:
            self._ensure_writer()
            self._queue.put_nowait((metadata.path, table_name, value, timestamp, ua_vtype.value))
            logger.debug(
                "hda.save_node_value.queued",
                path=metadata.path,
                value=value,
                mode=policy.mode.value if policy else "none",
            )

        # modo aggregate → acumula no buffer
        elif policy.is_aggregate:
            metadata.buffer.push(float(value), timestamp, policy.window_seconds)
            logger.debug(
                "hda.save_node_value.buffered",
                path=metadata.path,
                value=value,
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

        nó raw (sample/sem policy) → hypertable raw
        nó raw (aggregate)         → janelas gravadas, com o valor agregado
        nó virtual                 → view do level, com a média do bucket
                                     ex: Value@1hour → "{md5}_1hour"

        nb_values = 0 significa sem limite (OPC 10000-11): a resposta é
        paginada em MAX_HISTORY_VALUES. O continuation point é o timestamp do
        primeiro valor não devolvido, que o asyncua usa como novo StartTime.
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

        lower, upper, reverse = history_range(start, end)
        if lower is None and upper is None:
            logger.warning("hda.read_node_history.no_time_range", path=metadata.path)
            return [], None

        page = min(nb_values, MAX_HISTORY_VALUES) if nb_values else MAX_HISTORY_VALUES
        table_name = _table_name(raw_metadata)
        policy = raw_metadata.aggregation_policy
        level = metadata.level

        if level == "raw" and policy is not None and policy.is_aggregate:
            rows = await self._db.query_aggregate(
                table_name=table_name,
                start=lower,
                end=upper,
                limit=page + 1,
                window=policy.window,
                function=policy.function,
                reverse=reverse,
            )
            data_values = [_window_to_data_value(row) for row in rows]
        else:
            rows = await self._db.query(
                table_name=table_name,
                start=lower,
                end=upper,
                limit=page + 1,
                level=level,
                reverse=reverse,
            )
            data_values = [_row_to_data_value(row, level) for row in rows]

        logger.info(
            "hda.read_node_history",
            path=metadata.path,
            level=level,
            start=str(lower),
            end=str(upper),
            reverse=reverse,
            values=min(len(data_values), page),
        )

        continuation = None
        if len(data_values) > page:
            continuation = data_values[page].SourceTimestamp
            data_values = data_values[:page]

        return data_values, continuation

    async def _aggregate_window_loop(
        self,
        metadata: NodeMetadata,
        table_name: str,
    ) -> None:
        """Persiste cada janela logo após seu fim no relógio (UTC)."""
        policy = metadata.aggregation_policy
        window_seconds = policy.window_seconds

        logger.info(
            "hda.aggregate_window.started",
            id_short=metadata.id_short,
            window=policy.window,
            window_seconds=window_seconds,
        )

        while True:
            now = self._clock()
            boundary = bucket_start(now, window_seconds) + timedelta(seconds=window_seconds)
            await asyncio.sleep((boundary - now).total_seconds() + _FLUSH_GRACE_SECONDS)
            await self.flush(metadata, table_name)

    async def flush(
        self,
        metadata: NodeMetadata,
        table_name: str,
        include_open: bool = False,
    ) -> None:
        """
        Grava as janelas encerradas (ou todas, com include_open). Se o banco
        falhar, os agregados não gravados ficam para a próxima janela.
        """
        policy = metadata.aggregation_policy

        if include_open:
            results = metadata.buffer.take_all(policy.function)
        else:
            results = metadata.buffer.take_closed(self._clock(), policy.window_seconds, policy.function)

        for index, result in enumerate(results):
            try:
                await self._db.insert_aggregate(
                    table_name=table_name,
                    result=result,
                    window=policy.window,
                    function=policy.function,
                )
            except asyncio.CancelledError:
                metadata.buffer.retry(results[index:])
                raise
            except Exception as exc:
                dropped = metadata.buffer.retry(results[index:])
                logger.error(
                    "hda.flush_buffer.failed",
                    id_short=metadata.id_short,
                    pending=len(results) - index,
                    dropped=dropped,
                    error=str(exc),
                )
                return

            logger.info(
                "hda.flush_buffer.done",
                id_short=metadata.id_short,
                bucket=str(result.bucket),
                value=result.value,
                sample_count=result.sample_count,
                function=policy.function.value,
            )

    async def new_historized_event(self, source_id, evtypes, period, count=0):
        pass

    async def save_event(self, event):
        pass

    async def read_event_history(self, source_id, start, end, nb_values, evfilter):
        pass

    async def stop(self) -> None:
        # chamado pelo HDAManager e de novo pelo asyncua ao parar o servidor
        if self._stopped:
            return
        self._stopped = True

        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # a janela em aberto também é gravada: ao voltar, as amostras restantes
        # da mesma janela são combinadas com ela no banco
        for table_name, metadata in self._aggregates.items():
            await self.flush(metadata, table_name, include_open=True)

        try:
            await asyncio.wait_for(self.drain(), _DRAIN_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.error("hda.stop.samples_lost", samples=self._queue.qsize())

        if self._writer is not None:
            self._writer.cancel()
            await asyncio.gather(self._writer, return_exceptions=True)

        await self._db.disconnect()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _table_name(metadata: NodeMetadata) -> str:
    return build_table_name(build_index(metadata.submodel_id, metadata.path))


def _cast_db_value(value: float, vtype: VariantType):
    if vtype in (
        VariantType.Int16, VariantType.UInt16,
        VariantType.Int32, VariantType.UInt32,
        VariantType.Int64, VariantType.UInt64,
    ):
        return int(value)
    if vtype == VariantType.Boolean:
        return bool(value)
    return value  # Float, Double — mantém como float


def _row_to_data_value(row: dict, level: str) -> DataValue:
    if level == "raw":
        vtype = VariantType(row["variant_type"])
        val = _cast_db_value(row["value"], vtype)
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


def _window_to_data_value(row: dict) -> DataValue:
    return DataValue(
        Value=Variant(Value=row["value"], VariantType=VariantType.Double),
        SourceTimestamp=row["bucket"],
    )

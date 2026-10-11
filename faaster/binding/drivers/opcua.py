"""
Driver OPC UA (cliente) para interfaces do AID com base 'opc.tcp://…'.

Resolve cada ponto pelo NodeId do href ('?id=ns=3;s=…') e, na falta dele,
pelo uav_browsePath (relativo à pasta Objects). Pontos observáveis viram
monitored items de uma subscription; os demais são lidos por polling.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional

from asyncua import Client, Node, ua

from faaster.binding.drivers.base import IAssetDriver, ValueCallback
from faaster.binding.model import AssetInterface, PropertyAffordance
from faaster.log import get_logger


logger = get_logger(__name__)

_RECONNECT_DELAY = float(os.environ.get("FAASTER_BINDING_RECONNECT_DELAY", "5"))
_WATCHDOG_INTERVAL = float(os.environ.get("FAASTER_BINDING_WATCHDOG_INTERVAL", "2"))
_PUBLISHING_INTERVAL_MS = float(os.environ.get("FAASTER_BINDING_PUBLISHING_INTERVAL_MS", "10"))
_SUPPORTED_SECURITY = {"nosec"}


class _DataChangeHandler:
    def __init__(self, driver: "OpcUaDriver") -> None:
        self._driver = driver

    def datachange_notification(self, node: Node, value: Any, data: Any) -> None:
        affordance = self._driver._by_node_id.get(node.nodeid.to_string())
        if affordance is not None:
            self._driver._deliver(affordance, value)

    def status_change_notification(self, status: Any) -> None:
        logger.warning("binding.opcua.subscription_status", base=self._driver.interface.base, status=str(status))
        self._driver._connected = False


class OpcUaDriver(IAssetDriver):
    schemes = ["opc.tcp"]

    def __init__(self, interface: AssetInterface) -> None:
        super().__init__(interface)
        self._client: Optional[Client] = None
        self._connected = False
        self._nodes: Dict[str, Node] = {}
        self._by_node_id: Dict[str, PropertyAffordance] = {}
        self._data_types: Dict[str, ua.VariantType] = {}
        self._observe: List[PropertyAffordance] = []
        self._poll: Dict[str, float] = {}
        self._on_value: Optional[ValueCallback] = None
        self._tasks: List[asyncio.Task] = []
        self._session_tasks: List[asyncio.Task] = []
        self._lock = asyncio.Lock()
        # entrega em ordem: um único consumidor para todas as notificações
        self._queue: "asyncio.Queue[tuple]" = asyncio.Queue()

    # -------------------------------------------------------------------------
    # IAssetDriver
    # -------------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected

    async def start(
        self,
        observe: List[PropertyAffordance],
        on_value: ValueCallback,
        poll: Optional[Dict[str, float]] = None,
    ) -> None:
        unsupported = [s for s in self.interface.security_schemes if s not in _SUPPORTED_SECURITY]
        if unsupported:
            raise NotImplementedError(
                f"security scheme(s) {unsupported} not supported yet for {self.interface.base}"
            )

        self._observe = observe
        self._on_value = on_value
        self._poll = poll or {}

        try:
            await self._connect()
        except Exception as exc:
            logger.warning(
                "binding.opcua.first_connect_failed",
                base=self.interface.base,
                error=str(exc) or type(exc).__name__,
                retry_in=_RECONNECT_DELAY,
            )
        self._tasks.append(asyncio.create_task(self._consume(), name=f"binding:{self.interface.base}:values"))
        self._tasks.append(asyncio.create_task(self._watchdog(), name=f"binding:{self.interface.base}"))

    async def write(self, affordance: PropertyAffordance, value: Any) -> None:
        if not self._connected:
            raise ConnectionError(f"{self.interface.base} not connected")
        node = self._nodes[affordance.name]
        variant_type = self._data_types.get(affordance.name)
        if variant_type is None:
            variant_type = await node.read_data_type_as_variant_type()
            self._data_types[affordance.name] = variant_type
        await node.write_value(ua.DataValue(ua.Variant(_coerce(value, variant_type), variant_type)))

    async def stop(self) -> None:
        for task in self._tasks + self._session_tasks:
            task.cancel()
        await self._disconnect()

    # -------------------------------------------------------------------------
    # Conexão
    # -------------------------------------------------------------------------

    async def _connect(self) -> None:
        async with self._lock:
            await self._disconnect()
            client = Client(self.interface.base, timeout=_WATCHDOG_INTERVAL * 2)
            await client.connect()
            self._client = client

            self._nodes, self._by_node_id, self._data_types = {}, {}, {}
            for affordance in self._unique(self._observe + self._writable()):
                node = await self._resolve(affordance)
                if node is None:
                    continue
                self._nodes[affordance.name] = node
                self._by_node_id[node.nodeid.to_string()] = affordance

            subscribed = [
                self._nodes[a.name] for a in self._observe
                if a.name in self._nodes and a.name not in self._poll
            ]
            if subscribed:
                subscription = await client.create_subscription(
                    _PUBLISHING_INTERVAL_MS, _DataChangeHandler(self)
                )
                # a subscription entrega o valor atual de cada item ao criar
                await subscription.subscribe_data_change(subscribed)

            for affordance in self._observe:
                if affordance.name in self._poll and affordance.name in self._nodes:
                    self._session_tasks.append(asyncio.create_task(
                        self._polling(affordance, self._poll[affordance.name])
                    ))

            self._connected = True
            logger.info(
                "binding.opcua.connected",
                base=self.interface.base,
                resolved=len(self._nodes),
                subscribed=len(subscribed),
            )

    async def _disconnect(self) -> None:
        self._connected = False
        for task in self._session_tasks:
            task.cancel()
        self._session_tasks = []
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None

    async def _watchdog(self) -> None:
        while True:
            await asyncio.sleep(_WATCHDOG_INTERVAL if self._connected else _RECONNECT_DELAY)
            if self._connected:
                try:
                    await self._client.nodes.server_state.read_value()
                    continue
                except Exception as exc:
                    logger.warning("binding.opcua.connection_lost", base=self.interface.base, error=str(exc))
                    await self._disconnect()
                    continue  # espera _RECONNECT_DELAY antes de tentar de novo
            try:
                await self._connect()
                logger.info("binding.opcua.reconnected", base=self.interface.base)
            except Exception as exc:
                logger.warning(
                    "binding.opcua.reconnect_failed",
                    base=self.interface.base,
                    error=str(exc) or type(exc).__name__,
                    retry_in=_RECONNECT_DELAY,
                )

    async def _polling(self, affordance: PropertyAffordance, interval: float) -> None:
        node = self._nodes[affordance.name]
        while self._connected:
            try:
                self._deliver(affordance, await node.read_value())
            except Exception as exc:
                logger.warning("binding.opcua.poll_failed", point=affordance.name, error=str(exc))
            await asyncio.sleep(interval)

    # -------------------------------------------------------------------------
    # Resolução dos pontos
    # -------------------------------------------------------------------------

    async def _resolve(self, affordance: PropertyAffordance) -> Optional[Node]:
        try:
            if affordance.node_id:
                node = self._client.get_node(affordance.node_id)
                await node.read_browse_name()  # confirma que existe
                return node
            if affordance.browse_path:
                return await self._browse(affordance.browse_path)
        except Exception as exc:
            logger.error(
                "binding.opcua.unresolved",
                base=self.interface.base,
                point=affordance.name,
                href=affordance.href,
                browse_path=affordance.browse_path,
                error=str(exc) or type(exc).__name__,
            )
            return None
        logger.error("binding.opcua.no_address", base=self.interface.base, point=affordance.name)
        return None

    async def _browse(self, browse_path: str) -> Node:
        """
        'ns:Nome/ns:Nome/…' a partir de Objects. Segmentos sem índice de
        namespace casam pelo nome em qualquer namespace.
        """
        node = self._client.nodes.objects
        for segment in browse_path.strip("/").split("/"):
            if ":" in segment and segment.split(":", 1)[0].isdigit():
                node = await node.get_child(segment)
                continue
            for candidate in await node.get_children():
                if (await candidate.read_browse_name()).Name == segment:
                    node = candidate
                    break
            else:
                raise ua.UaError(f"'{segment}' not found under {node.nodeid.to_string()}")
        return node

    # -------------------------------------------------------------------------
    # Utilidades
    # -------------------------------------------------------------------------

    def _writable(self) -> List[PropertyAffordance]:
        """Todos os pontos do AID — qualquer um pode ser alvo de escrita."""
        return list(self.interface.properties.values())

    @staticmethod
    def _unique(affordances: List[PropertyAffordance]) -> List[PropertyAffordance]:
        return list({a.name: a for a in affordances}.values())

    def _deliver(self, affordance: PropertyAffordance, value: Any) -> None:
        self._queue.put_nowait((affordance, value))

    async def _consume(self) -> None:
        while True:
            affordance, value = await self._queue.get()
            try:
                await self._on_value(affordance, value)
            except Exception as exc:
                logger.error("binding.opcua.deliver_failed", point=affordance.name, error=str(exc))


_INTEGER_TYPES = {
    ua.VariantType.SByte, ua.VariantType.Byte,
    ua.VariantType.Int16, ua.VariantType.UInt16,
    ua.VariantType.Int32, ua.VariantType.UInt32,
    ua.VariantType.Int64, ua.VariantType.UInt64,
}


def _coerce(value: Any, variant_type: ua.VariantType) -> Any:
    """Valor do AAS → tipo Python esperado pelo nó do ativo."""
    if variant_type == ua.VariantType.Boolean:
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1")
        return bool(value)
    if variant_type in _INTEGER_TYPES:
        return int(value)
    if variant_type in (ua.VariantType.Float, ua.VariantType.Double):
        return float(value)
    if variant_type == ua.VariantType.String:
        return str(value)
    return value

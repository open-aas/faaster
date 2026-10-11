from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, List, Optional, Type

from faaster.binding.model import AssetInterface, PropertyAffordance
from faaster.log import get_logger


logger = get_logger(__name__)

#: grupo de entry points para drivers de terceiros:
#:   [project.entry-points."faaster.bindings"]
#:   "modbus+tcp" = "meu_pacote.modbus:ModbusDriver"
ENTRY_POINT_GROUP = "faaster.bindings"

ValueCallback = Callable[[PropertyAffordance, Any], Awaitable[None]]


class IAssetDriver(ABC):
    """
    Conexão com uma interface de ativo descrita no AID.

    O driver é dono da conexão: reconecta sozinho e, a cada (re)conexão,
    entrega de novo os valores observados — o binder não precisa saber
    se houve queda.
    """

    #: esquemas de URI atendidos pelo driver (base do EndpointMetadata)
    schemes: List[str] = []

    def __init__(self, interface: AssetInterface) -> None:
        self.interface = interface

    @abstractmethod
    async def start(
        self,
        observe: List[PropertyAffordance],
        on_value: ValueCallback,
        poll: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Conecta e passa a entregar on_value(affordance, valor) para cada
        ponto em observe. Pontos com intervalo em poll (segundos, por nome)
        são lidos periodicamente em vez de subscritos.
        """
        ...

    @abstractmethod
    async def write(self, affordance: PropertyAffordance, value: Any) -> None:
        """Escreve no ativo. Levanta exceção se não for possível."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @property
    @abstractmethod
    def connected(self) -> bool:
        ...


def _builtin_drivers() -> Dict[str, Type[IAssetDriver]]:
    from faaster.binding.drivers.opcua import OpcUaDriver
    return {scheme: OpcUaDriver for scheme in OpcUaDriver.schemes}


def load_drivers() -> Dict[str, Type[IAssetDriver]]:
    """Drivers embutidos + os registrados por entry point (estes têm prioridade)."""
    from importlib.metadata import entry_points

    drivers = _builtin_drivers()
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            drivers[ep.name] = ep.load()
            logger.info("binding.driver.registered", scheme=ep.name, driver=ep.value)
        except Exception as exc:
            logger.error("binding.driver.load_failed", scheme=ep.name, error=str(exc))
    return drivers

from typing import List
from faaster.parser.node_registry import NodeRegistry
from faaster.interfaces.idatabase import IDatabase
from faaster.interfaces.idatabase import IHDAManager
from .storage import TimescaleHDAStorage
from faaster.interfaces import IOPCUAServer, INode
from faaster.log import get_logger

logger = get_logger(__name__)


class HDAManager(IHDAManager):

    def __init__(
        self,
        server: IOPCUAServer,
        db: IDatabase,
        registry: NodeRegistry,
    ) -> None:
        self._server = server
        self._db = db
        self._registry = registry
        self._storage = TimescaleHDAStorage(
            db=db,
            registry=registry,
        )

    async def init(self, nodes: List[INode]) -> None:
        logger.info("hda_manager.init.start", nodes=len(nodes))

        await self._storage.init()
        await self._server.set_history_storage(self._storage)

        for node in nodes:
            await self._server.historize_node(node)

        logger.info("hda_manager.init.done", nodes=len(nodes))

    async def stop(self) -> None:
        logger.info("hda_manager.stop")
        await self._storage.stop()

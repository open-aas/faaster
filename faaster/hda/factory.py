from faaster.infra.database_timescale import  TimescaleDatabase
from faaster.parser.node_registry import NodeRegistry
from faaster.interfaces.idatabase import IHDAManager
from faaster.interfaces import IOPCUAServer
from faaster.log import get_logger
from .manager import HDAManager

logger = get_logger(__name__)


class HDAManagerFactory:

    @staticmethod
    def create(
        backend: str,
        url: str,
        db_name: str,
        server: IOPCUAServer,
        registry: NodeRegistry,
    ) -> IHDAManager:
        logger.info(
            "hda_factory.create",
            backend=backend,
            db_name=db_name,
        )

        if str(backend) == "timescaledb":
            db = TimescaleDatabase(url=url, db_name=db_name)
            return HDAManager(
                server=server,
                db=db,
                registry=registry,
            )

        if str(backend) == "mongodb":
            raise NotImplementedError(
                "MongoDB HDA backend not yet implemented. "
                "Use timescaledb."
            )

        raise ValueError(f"Unknown HDA backend: '{backend}'")

from argparse import Namespace
from datetime import datetime
from typing import Optional, List
from asyncua import Server
from asyncua.ua import BuildInfo

from faaster.extensions import ExtensionLoader
from faaster.interfaces import IOPCUAServer, IAddressSpace
from faaster.log import get_logger
from faaster.interfaces import INode
from faaster.interfaces.ihda import IHDAStorage, IHDAManager
from faaster.parser import AASParser

import asyncio


logger = get_logger(__name__)


class OPCUAServer(IOPCUAServer):
    def __init__(
        self,
        opcua_server: Server,
        address_space: IAddressSpace,
        parser: AASParser,
        extension_loader: ExtensionLoader,
        hda_manager: Optional[IHDAManager] = None,
    ) -> None:
        self._uri = "urn:faaster:server"
        self._opcua_server = opcua_server
        self._address_space = address_space
        self._parser = parser
        self._hda_manager = hda_manager
        self._stop_event = asyncio.Event()
        self._historized_nodes: list = []
        self._extension_loader = extension_loader
        self._extensions_tasks: List[asyncio.Task] = []

    async def set_history_storage(self, storage: IHDAStorage) -> None:
        self._opcua_server.iserver.history_manager.set_storage(storage)

    async def historize_node(self, node: INode) -> None:
        await self._opcua_server.iserver.enable_history_data_change(node.raw)

    @property
    def address_space(self) -> IAddressSpace:
        return self._address_space

    @property
    def hda_manager(self) -> Optional[IHDAManager]:
        return self._hda_manager

    @hda_manager.setter
    def hda_manager(self, hda_manager: IHDAManager):
        self._hda_manager = hda_manager

    async def setup(self, args: Namespace) -> None:
        logger.info("opcua_server.setup.start")
        self._args = args

        await self._opcua_server.init()
        await self._opcua_server.register_namespace(self._uri)
        self._address_space.set_namespace(self._uri)

        endpoint = f"opc.tcp://{args.host}:{args.port}"
        self._opcua_server.set_endpoint(endpoint)
        self._opcua_server.set_server_name(args.product_name)
        await self._configure_build_info(args)

        logger.info(
            "opcua_server.setup.done",
            endpoint=endpoint,
            product_name=args.product_name,
        )

    async def build_address_space(self, modeling_file: str) -> None:
        logger.info(
            "opcua_server.build_address_space.start",
            modeling_file=modeling_file,
        )

        logger.info(
            "opcua_server.build_address_space.start",
            modeling_file=modeling_file,
        )

        self._historized_nodes = await self._parser.parse(modeling_file)

        logger.info(
            "opcua_server.build_address_space.done",
            historized_nodes=len(self._historized_nodes),
        )

    async def load_extension(self) -> None:
        """
        Delegado ao ExtensionLoader — o servidor apenas
        expõe o address_space para que a extensão possa
        interagir com os nós existentes.
        """
        logger.info("opcua_server.load_extension.start")

        loaded = await self._extension_loader.load(self)

        logger.info(
            "opcua_server.load_extension.done",
            loaded=list(loaded.keys()),
        )

        logger.info("opcua_server.load_extension.done")

    async def init_hda(self) -> None:
        if not self._historized_nodes:
            logger.info("opcua_server.init_hda.skipped.no_nodes")
            return

        if self._hda_manager is None:
            logger.warning(
                "opcua_server.init_hda.skipped.no_manager",
                reason="No IHDAManager provided. HDA will not be initialized.",
            )
            return

        logger.info(
            "opcua_server.init_hda.start",
            nodes=len(self._historized_nodes),
        )

        await self._hda_manager.init(self._historized_nodes)

        logger.info("opcua_server.init_hda.done")

    async def run(self) -> None:
        logger.info("opcua_server.run.start")

        async with self._opcua_server:
            logger.info("opcua_server.run.listening")

            if self._args.url_discovery:
                asyncio.create_task(
                    self._register_lds(),
                    name="faaster.lds_registration",
                )

            for name, extension in self._extension_loader.instances.items():
                task = asyncio.create_task(extension.init(), name=f'TaskSubmodel:{name}')
                self._extensions_tasks.append(task)

            await self._stop_event.wait()

        logger.info("opcua_server.run.stopped")

    async def stop(self) -> None:
        logger.info("opcua_opcua_server.stop")
        for name, extension in self._extension_loader.instances:
            extension.stop()

        for task in self._extensions_tasks:
            if not task.done():
                task.cancel()

        self._stop_event.set()

    async def _register_lds(self) -> None:
        """
        Registra o servidor no LDS periodicamente.
        O OPC UA exige re-registro a cada 10 minutos.
        """
        url = self._args.url_discovery
        interval = 600

        while not self._stop_event.is_set():
            try:
                await self._opcua_server.register_to_discovery(url)
                logger.info(
                    "opcua_server.lds.registered",
                    url=url,
                )
            except Exception as e:
                logger.warning(
                    "opcua_server.lds.failed",
                    url=url,
                    error=str(e),
                )

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=interval,
                )
            except asyncio.TimeoutError:
                pass

    async def _configure_build_info(self, args: Namespace) -> None:
        build_info = BuildInfo()
        build_info.ProductUri = args.product_uri
        build_info.ManufacturerName = args.manufacturer_name
        build_info.ProductName = args.product_name
        build_info.SoftwareVersion = args.software_version
        build_info.BuildNumber = args.build_number
        build_info.BuildDate = datetime.fromisoformat(
            args.build_date.replace("Z", "+00:00")
        )

        await self._opcua_server.set_build_info(
            product_uri=build_info.ProductUri,
            manufacturer_name=build_info.ManufacturerName,
            product_name=build_info.ProductName,
            software_version=build_info.SoftwareVersion,
            build_number=build_info.BuildNumber,
            build_date=build_info.BuildDate,
        )

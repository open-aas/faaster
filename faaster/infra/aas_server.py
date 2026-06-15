from argparse import Namespace
from datetime import datetime
from typing import Optional, List
from asyncua import Server, Client
from asyncua.ua import BuildInfo, RegisteredServer, ApplicationType, LocalizedText, EndpointType

from faaster.extensions import ExtensionLoader
from faaster.gds import GDSClient, GDSCertificateClient, GDSRegistrationManager, ApplicationRecord
from faaster.interfaces import IOPCUAServer, IAddressSpace
from faaster.security import (
    CertificateStore,
    CertificateManager,
    SecurityMode,
    bootstrap_pki,
    build_security_policy_list,
    configure_server_security,
    auto_accept_task,
)
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
        self._trust_store = None  # definido em setup() quando --pki-dir é fornecido

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

        if getattr(args, "pki_dir", None):
            await self._setup_security(args)

        logger.info(
            "opcua_server.setup.done",
            endpoint=endpoint,
            product_name=args.product_name,
        )

    async def _setup_security(self, args: Namespace) -> None:
        """
        Configura PKI e políticas de segurança OPC UA.

        Pode ser standalone (self-signed + políticas locais) ou integrado
        ao GDS quando --gds-url também estiver configurado.
        """
        store = CertificateStore(pki_dir=args.pki_dir)

        common_name = getattr(args, "cert_common_name", None) or args.product_name
        application_uri = self._opcua_server.get_application_uri()

        await bootstrap_pki(
            store=store,
            common_name=common_name,
            application_uri=application_uri,
            san_dns=getattr(args, "cert_san_dns", None),
            san_ips=getattr(args, "cert_san_ips", None),
        )

        policies = build_security_policy_list(
            policies=getattr(args, "security_policy", None),
            mode=getattr(args, "security_mode", None) or SecurityMode.sign_and_encrypt,
            allow_anonymous=getattr(args, "allow_anonymous", False),
        )

        self._trust_store = await configure_server_security(
            opcua_server=self._opcua_server,
            store=store,
            policies=policies,
        )

        # Guarda o store para reutilização na task de auto-accept e no CertificateManager
        self._cert_store = store

        logger.info(
            "opcua_server.security_configured",
            pki_dir=args.pki_dir,
            policy_count=len(policies),
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

            if self._args.server_discovery:
                asyncio.create_task(
                    self._register_lds(),
                    name="faaster.lds_registration",
                )

            if self._args.gds_url:
                asyncio.create_task(
                    self._register_gds(),
                    name="faaster.gds_registration",
                )

            if self._args.gds_url and getattr(self._args, "pki_dir", None):
                asyncio.create_task(
                    self._manage_certificates(),
                    name="faaster.certificate_management",
                )

            if getattr(self._args, "auto_accept_clients", False) and self._trust_store:
                asyncio.create_task(
                    auto_accept_task(
                        store=self._cert_store,
                        trust_store=self._trust_store,
                        stop_event=self._stop_event,
                    ),
                    name="faaster.auto_accept_clients",
                )

            for name, extension in self._extension_loader.instances.items():
                task = asyncio.create_task(extension.init(), name=f'TaskSubmodel:{name}')
                self._extensions_tasks.append(task)

            await self._stop_event.wait()

        logger.info("opcua_server.run.stopped")

    async def stop(self) -> None:
        logger.info("opcua_opcua_server.stop")
        for name, extension in self._extension_loader.instances.items():
            extension.stop()

        for task in self._extensions_tasks:
            if not task.done():
                task.cancel()

        self._stop_event.set()

    async def _register_gds(self) -> None:
        """Registra o servidor no GDS e mantém o registro ativo (OPC 10000-12 §6.4)."""
        args = self._args

        record = ApplicationRecord(
            application_uri=self._opcua_server.get_application_uri(),
            application_type=ApplicationType.Server,
            application_names=[LocalizedText(Text=args.product_name, Locale="pt-br")],
            product_uri=args.product_uri,
            discovery_urls=[args.discovery_url],
            server_capabilities=[],
        )

        client = GDSClient(
            url=args.gds_url,
            username=getattr(args, "gds_username", None),
            password=getattr(args, "gds_password", None),
        )
        manager = GDSRegistrationManager(
            client=client,
            record=record,
            renew_interval=args.renew_interval,
        )

        await manager.run(self._stop_event)

    async def _manage_certificates(self) -> None:
        """
        Gerencia o ciclo de vida de certificados via GDS Pull Management
        (OPC 10000-12 §7.9).

        Registra a aplicação no GDS para obter o applicationId, depois delega
        ao CertificateManager o bootstrap, emissão e renovação de certificados.
        Cada sessão GDS (registro, emissão, TrustList) abre/fecha a conexão
        de forma independente.
        """
        args = self._args
        store = CertificateStore(pki_dir=args.pki_dir)
        common_name = getattr(args, "cert_common_name", None) or args.product_name
        application_uri = self._opcua_server.get_application_uri()

        record = ApplicationRecord(
            application_uri=application_uri,
            application_type=ApplicationType.Server,
            application_names=[LocalizedText(Text=args.product_name, Locale="pt-br")],
            product_uri=args.product_uri,
            discovery_urls=[args.discovery_url],
            server_capabilities=[],
        )

        gds_client = GDSCertificateClient(
            url=args.gds_url,
            username=getattr(args, "gds_username", None),
            password=getattr(args, "gds_password", None),
        )

        # Registro inicial — GDSRegistrationManager gerencia sua própria sessão
        reg_manager = GDSRegistrationManager(
            client=gds_client,
            record=record,
            renew_interval=args.renew_interval,
        )
        try:
            await reg_manager.register()
        except Exception:
            logger.exception("certificate_manager.registration_failed")
            return

        cert_manager = CertificateManager(
            gds_client=gds_client,
            store=store,
            record=record,
            common_name=common_name,
            application_uri=application_uri,
            san_dns=getattr(args, "cert_san_dns", None),
            san_ips=getattr(args, "cert_san_ips", None),
        )

        await cert_manager.run(self._stop_event, renew_interval=args.renew_interval)

    async def _register_lds(self) -> None:
        """
        Registra o servidor no LDS periodicamente.
        O OPC UA exige re-registro a cada 10 minutos.
        """
        url = self._args.server_discovery
        interval = self._args.renew_interval

        while not self._stop_event.is_set():
            client = Client(url)
            try:
                await client.connect()
                serv = RegisteredServer()
                print(self._opcua_server.get_application_uri())

                serv.ServerUri = self._opcua_server.get_application_uri()
                serv.ProductUri = self._args.product_uri
                serv.DiscoveryUrls = [self._args.discovery_url]
                serv.ServerType = ApplicationType.Server
                serv.ServerNames = [LocalizedText(Text=self._args.product_name, Locale='pt-br')]
                serv.IsOnline = True

                await client.uaclient.register_server(serv)

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

            else:
                await client.disconnect()

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

        self._opcua_server.set_server_name(args.product_name)
        await self._opcua_server.set_application_uri(build_info.ProductUri)

        await self._opcua_server.set_build_info(
            product_uri=build_info.ProductUri,
            manufacturer_name=build_info.ManufacturerName,
            product_name=build_info.ProductName,
            software_version=build_info.SoftwareVersion,
            build_number=build_info.BuildNumber,
            build_date=build_info.BuildDate,
        )

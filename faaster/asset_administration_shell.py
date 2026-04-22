from argparse import Namespace
from typing import Optional, Dict
from asyncua import Server
from faaster.interfaces import IOPCUAServer, IAddressSpace
from faaster.infra.aas_server import OPCUAServer
from faaster.infra.address_space import AddressSpaceAdapter
from faaster.log import get_logger
from faaster.interfaces.idatabase import IHDAManager
from faaster.parser.element_creator import AASElementCreator
from faaster.parser.creators import (
    AASCreator,
    SubmodelCreator,
    PropertyCreator,
    OperationCreator,
    CollectionCreator,
    RangeCreator,
    MultiLanguagePropertyCreator,
    ReferenceElementCreator,
    FileCreator,
    BasicEventElementCreator,
    ConceptDescriptionCreator,
)
from faaster.parser import AASParser, NodeRegistry
from faaster.hda import HDAManagerFactory
from faaster.extensions.interfaces import ISubmodelExtension
from faaster.extensions.loader import ExtensionLoader

logger = get_logger(__name__)


FAASTER_NAMESPACE_URI = "urn:faaster:server"


class AssetAdministrationShell:
    """
    Container de dependências do Faaster.

    Instancia e conecta todas as implementações concretas,
    delegando ao main.py apenas a chamada do ciclo de vida.

    Uso:
        aas = AssetAdministrationShell(args)
        await aas.server.setup(args)
        await aas.server.build_address_space(args.modeling_file)
        await aas.server.load_extension(args.config_sensor)
        await aas.server.init_hda()
        await aas.server.run()
    """

    def __init__(self, args: Namespace) -> None:
        self._args = args
        self._opcua_server = Server()
        self._address_space = AddressSpaceAdapter(self._opcua_server)
        self._hda_manager: Optional[IHDAManager] = None
        self._registry = NodeRegistry()

        self._element_creator = AASElementCreator(
            aas=AASCreator(),
            submodel=SubmodelCreator(),
            prop=PropertyCreator(),
            operation=OperationCreator(),
            collection=CollectionCreator(),
            rg=RangeCreator(),
            mlp=MultiLanguagePropertyCreator(),
            reference_element=ReferenceElementCreator(),
            file=FileCreator(),
            event=BasicEventElementCreator(),
            concept_description=ConceptDescriptionCreator(),
        )

        self._parser = AASParser(
            address_space=self._address_space,
            creator=self._element_creator,
            node_registry=self._registry
        )

        self._extension_loader = ExtensionLoader(self._address_space, self._registry)

        self._server = OPCUAServer(
            opcua_server=self._opcua_server,
            address_space=self._address_space,
            parser=self._parser,
            hda_manager=self._hda_manager,
            extension_loader=self._extension_loader
        )

        if args.url_database:
            self._hda_manager = HDAManagerFactory.create(
                backend=args.db_backend,
                url=args.url_database,
                db_name=args.db_name or args.aas_id,
                server=self._server,
                registry=self._registry,
            )

            self._server.hda_manager = self._hda_manager

    @property
    def server(self) -> IOPCUAServer:
        """Ponto de entrada do ciclo de vida do Faaster."""
        return self._server

    @property
    def address_space(self) -> IAddressSpace:
        """
        Exposto para uso pelo parser e pelo script customizado
        fora do ciclo de vida do servidor.
        """
        return self._address_space

    @property
    def parser(self) -> AASParser:
        return self._parser

    @property
    def node_registry(self) -> NodeRegistry:
        return self._registry

    @property
    def extensions(self) -> Dict[str, ISubmodelExtension]:
        return self._extension_loader.instances

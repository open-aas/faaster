from pathlib import Path
from typing import List, Optional

from .creators.base import resolve_variant_type
from .creators.property_creator import PropertyCreator
from faaster.loader.factory import LoaderFactory
from faaster.aas_metamodel.models.environment import Environment
from faaster.aas_metamodel.models.submodel import Submodel
from faaster.aas_metamodel.models.concept_description import ConceptDescription
from faaster.aas_metamodel.models.asset_administration_shell import AssetAdministrationShell as AASModel
from faaster.aas_metamodel.models.submodel_element import SubmodelElement
from faaster.aas_metamodel.models.submodel_element_collection import SubmodelElementCollection
from faaster.aas_metamodel.models.operation import Operation
from faaster.aas_metamodel.submodel_element_processor import SubmodelElementProcessor
from faaster.interfaces import IAddressSpace, IElementCreator, INode
from faaster.interfaces.types import FaasterVariantType
from faaster.hda import HDAMode, extract_policy, AggregationPolicy
from faaster.log import get_logger
from .node_registry import NodeMetadata, NodeRegistry

logger = get_logger(__name__)


_DATA_ELEMENT_TYPES = {
    "Property",
    "MultiLanguageProperty",
    "Range",
    "File",
    "Blob",
    "ReferenceElement",
    "BasicEventElement",
}

_VARIABLE_CATEGORY = "VARIABLE"


class AASParser:
    """
    Realiza o parser do metamodelo AAS V3 e monta o espaço
    de endereços OPC UA delegando a criação de cada elemento
    ao IElementCreator.

    Retorna a lista de INode marcados como VARIABLE para
    posterior inicialização do HDA.
    """

    def __init__(
        self,
        address_space: IAddressSpace,
        creator: IElementCreator,
        node_registry: NodeRegistry,
    ) -> None:
        self._address_space = address_space
        self._creator = creator
        self._node_registry = node_registry
        self._historized_nodes: List[INode] = []
        self._environment: Optional[Environment] = None
        self._document: Optional[dict] = None
        self._root: Optional[INode] = None
        # False nas alterações em tempo de execução: o HDA só é montado na partida
        self._historize = True

    @property
    def environment(self) -> Optional[Environment]:
        """Environment validado do último parse()."""
        return self._environment

    @property
    def document(self) -> Optional[dict]:
        """Documento AAS V3 original (JSON) do último parse()."""
        return self._document

    async def parse(self, modeling_file: str) -> List[INode]:
        """
        Ponto de entrada do parser.

        1. Carrega o arquivo via LoaderFactory
        2. Cria o nó raiz Environment
        3. Percorre AAS → Submodels → SubmodelElements recursivamente
        4. Percorre ConceptDescriptions
        5. Retorna os nós VARIABLE para o HDA
        """
        self._historized_nodes = []

        logger.info("aas_parser.parse.start", modeling_file=modeling_file)

        loader = LoaderFactory.create(modeling_file)
        environment = await loader.load(Path(modeling_file))
        self._environment = environment
        self._document = loader.document
        root = await self._create_environment_node(environment)
        self._root = root

        await self._parse_aas_list(root, environment)
        await self._parse_submodel_list(root, environment)
        await self._parse_concept_description_list(root, environment)

        logger.info(
            "aas_parser.parse.done",
            modeling_file=modeling_file,
            historized_nodes=len(self._historized_nodes),
        )

        return self._historized_nodes

    async def _create_environment_node(self, environment: Environment) -> INode:
        """Cria o nó raiz Environment no espaço de endereços."""
        objects_node = await self._address_space.get_objects_node()
        root = await self._address_space.add_folder(objects_node, "Environment")

        logger.info("aas_parser.environment_node.created")
        return root

    # -------------------------------------------------------------------------
    # AAS
    # -------------------------------------------------------------------------

    async def _parse_aas_list(
        self,
        parent: INode,
        environment: Environment,
    ) -> None:
        if not environment.asset_administration_shells:
            return

        for aas in environment.asset_administration_shells:
            await self._parse_aas(parent, aas)

    async def _parse_aas(
        self,
        parent: INode,
        aas: AASModel,
    ) -> None:
        logger.info("aas_parser.aas.start", id_short=aas.id_short, id=aas.id)

        self._node_registry.set_aas_id_short(aas.id_short)

        await self._creator.create_aas(
            parent=parent,
            element=aas,
            address_space=self._address_space,
        )

        logger.info("aas_parser.aas.done", id_short=aas.id_short)

    # -------------------------------------------------------------------------
    # Submodels
    # -------------------------------------------------------------------------

    async def _parse_submodel_list(
        self,
        parent: INode,
        environment: Environment,
    ) -> None:
        if not environment.submodels:
            return

        for submodel in environment.submodels:
            await self._parse_submodel(parent, submodel)

    async def _parse_submodel(
        self,
        parent: INode,
        submodel: Submodel,
    ) -> None:
        logger.info(
            "aas_parser.submodel.start",
            id_short=submodel.id_short,
            id=submodel.id,
        )

        submodel_node = await self._creator.create_submodel(
            parent=parent,
            element=submodel,
            address_space=self._address_space,
        )

        self._node_registry.register_submodel_node(submodel.id_short, submodel_node)
        self._node_registry.register_element_node(submodel.id, "", submodel_node)

        if submodel.submodel_elements:
            await self._parse_submodel_elements(
                parent=submodel_node,
                elements=submodel.submodel_elements,
                submodel_id=submodel.id,
                current_path=submodel.id_short or "Submodel",  # ← raiz do path
            )

        logger.info("aas_parser.submodel.done", id_short=submodel.id_short)

    # -------------------------------------------------------------------------
    # SubmodelElements — travessia recursiva
    # -------------------------------------------------------------------------

    async def _parse_submodel_elements(
        self,
        parent: INode,
        elements: List[SubmodelElement],
        submodel_id,
        current_path: str,
    ) -> None:
        for element in elements:
            await self._parse_submodel_element(parent, element, submodel_id, current_path)

    async def _parse_submodel_element(
        self,
        parent: INode,
        element: SubmodelElement,
        submodel_id: str,
        current_path: str,
    ) -> None:

        if isinstance(element, dict):
            submodel_element_module, model_type = SubmodelElementProcessor.process_elements(element)
            cls = getattr(submodel_element_module, model_type)
            element = cls(**element)

        else:
            model_type = element.type_model

        logger.info(
            "aas_parser.element.start",
            id_short=element.id_short,
            model_type=model_type,
        )

        if model_type == "SubmodelElementCollection":
            await self._parse_collection(parent, element, submodel_id, current_path)

        elif model_type == "Operation":
            await self._parse_operation(parent, element, submodel_id, current_path)

        elif model_type in _DATA_ELEMENT_TYPES:
            await self._parse_data_element(parent, element, submodel_id, current_path)

        else:
            logger.warning(
                "aas_parser.element.unknown_type",
                id_short=element.id_short,
                model_type=model_type,
            )

    async def _parse_collection(
        self,
        parent: INode,
        element: SubmodelElement,
        submodel_id: str,
        current_path: str,
    ) -> None:
        collection = SubmodelElementCollection(**element.model_dump())

        collection_node = await self._creator.create_submodel_element_collection(
            parent=parent,
            element=collection,
            address_space=self._address_space,
        )
        self._register_element_node(submodel_id, current_path, collection.id_short, collection_node)

        if collection.value:
            await self._parse_submodel_elements(
                parent=collection_node,
                elements=collection.value,
                submodel_id=submodel_id,
                current_path=f"{current_path}/{element.id_short}",  # ← acumula
            )

    async def _parse_operation(
        self,
        parent: INode,
        element: SubmodelElement,
        submodel_id: str,
        current_path: str,
    ) -> None:
        operation = Operation(**element.model_dump())
        submodel_id_short, *parents = current_path.split("/")

        method_node, binder = await self._creator.create_operation(
            parent=parent,
            element=operation,
            address_space=self._address_space,
        )

        if method_node is not None and operation.id_short:
            self._register_element_node(
                submodel_id, current_path, operation.id_short, await method_node.get_parent()
            )
            self._node_registry.register_operation(
                submodel_id_short=submodel_id_short,
                id_short=operation.id_short,
                method_node=method_node,
                binder=binder,
                submodel_id=submodel_id,
                id_short_path=".".join([*parents, operation.id_short]),
            )

    async def _parse_data_element(
        self,
        parent: INode,
        element: SubmodelElement,
        submodel_id: str,
        current_path: str,
    ) -> None:
        model_type = element.type_model

        creator_map = {
            "Property": self._creator.create_property,
            "MultiLanguageProperty": self._creator.create_multi_language_property,
            "Range": self._creator.create_range,
            "File": self._creator.create_file,
            "ReferenceElement": self._creator.create_reference_element,
            "BasicEventElement": self._creator.create_basic_event_element,
        }

        creator_fn = creator_map.get(model_type)

        if creator_fn is None:
            logger.warning(
                "aas_parser.data_element.unknown_type",
                id_short=element.id_short,
                model_type=model_type,
            )
            return

        node = await creator_fn(
            parent=parent,
            element=element,
            address_space=self._address_space,
        )

        if node is not None and element.id_short:
            # Property devolve o nó Value; o elemento é o Object pai
            element_node = await node.get_parent() if model_type == "Property" else node
            self._register_element_node(submodel_id, current_path, element.id_short, element_node)

        if model_type == "Property" and node is not None and element.id_short:
            # current_path = "<SubmodelIdShort>/<Coll>/..." → idShortPath "Coll.Prop"
            parents = current_path.split("/")[1:]
            self._node_registry.register_value_node(
                submodel_id=submodel_id,
                id_short_path=".".join([*parents, element.id_short]),
                node=node,
                value_type=element.value_type,
            )

        if element.category == _VARIABLE_CATEGORY and node is not None and self._historize:
            # monta o path relativo ao submodel
            path = f"{current_path}/{element.id_short}/Value"

            # extrai o semantic_id se existir
            semantic_id = None

            if element.semantic_id:
                keys = element.semantic_id.keys
                if keys:
                    semantic_id = keys[0].value

            # resolve o variant_type
            variant_type = resolve_variant_type(element.value_type)

            #extrai o nome do submodel via path
            submodel_name = path.split("/")[0]
            policy = extract_policy(element.extensions)
            metadata = NodeMetadata(
                node=node,
                path=path,
                id_short=element.id_short or "",
                submodel=submodel_name,
                submodel_id=submodel_id,
                category=element.category or "VARIABLE",
                variant_type=variant_type,
                semantic_id=semantic_id,
                aggregation_policy=policy
            )

            self._node_registry.register(metadata)
            self._historized_nodes.append(node)

            virtual_nodes, _ = await PropertyCreator.create_virtual_nodes(
                parent=(await node.get_parent()),
                element=element,
                address_space=self._address_space,
            )

            for vnode, level in virtual_nodes:
                metadata = NodeMetadata(
                    node=vnode,
                    path=f'{path}@{level}',
                    id_short=f"Value@{level}",
                    submodel=submodel_name,
                    submodel_id=submodel_id,
                    category=element.category or "VARIABLE",
                    variant_type=FaasterVariantType.Double,
                    semantic_id=semantic_id,
                    level=level,
                )

                self._node_registry.register(metadata)

    def _register_element_node(
        self,
        submodel_id: str,
        current_path: str,
        id_short: Optional[str],
        node: INode,
    ) -> None:
        if not id_short:
            return
        parents = current_path.split("/")[1:]
        self._node_registry.register_element_node(submodel_id, ".".join([*parents, id_short]), node)

    # -------------------------------------------------------------------------
    # Alterações estruturais em tempo de execução (API HTTP/REST)
    #
    # Reaproveitam a mesma travessia da partida, mas sem historizar: o HDA
    # monta suas tabelas só na partida. Os elementos criados aqui ganham nós
    # de valor (leitura/escrita via API e OPC UA), mas não são historizados.
    # -------------------------------------------------------------------------

    async def add_submodel(self, submodel: Submodel) -> None:
        if self._root is None:
            raise RuntimeError("parse() must run before runtime changes")
        self._historize = False
        try:
            await self._parse_submodel(self._root, submodel)
        finally:
            self._historize = True

    async def add_submodel_element(
        self,
        submodel_id: str,
        submodel_id_short: str,
        parent_path: str,
        element: SubmodelElement,
    ) -> None:
        """
        Cria o elemento sob o submodelo (parent_path "") ou coleção. Elementos
        cujo pai não tem nó OPC UA (ex.: dentro de SubmodelElementList) só
        existem no modelo — como na partida.
        """
        parent = self._node_registry.get_element_node(submodel_id, parent_path)
        if parent is None:
            return

        current_path = "/".join([submodel_id_short or "Submodel", *filter(None, parent_path.split("."))])
        self._historize = False
        try:
            await self._parse_submodel_element(parent, element, submodel_id, current_path)
        finally:
            self._historize = True

    async def remove(self, submodel_id: str, id_short_path: str = "") -> None:
        """Remove do address space o submodelo ("") ou elemento, com toda a subárvore."""
        node = self._node_registry.get_element_node(submodel_id, id_short_path)
        if node is not None:
            await self._address_space.delete_node(node, recursive=True)
        self._node_registry.remove_subtree(submodel_id, id_short_path)

    async def refresh_metadata(self, submodel_id: str, id_short_path: str, element) -> None:
        """
        Recria só os nós de metadados de um Submodel, SubmodelElementCollection
        ou Property, preservando filhos e nós de valor — e, com eles, os
        NodeIds, as assinaturas OPC UA e o HDA.
        """
        node = self._node_registry.get_element_node(submodel_id, id_short_path)
        if node is None:
            return

        keep = {
            n.node_id
            for n in [
                *self._node_registry.child_element_nodes(submodel_id, id_short_path),
                *self._node_registry.runtime_value_nodes(submodel_id, id_short_path),
            ]
        }
        for child in await node.get_children():
            if child.node_id not in keep:
                await self._address_space.delete_node(child, recursive=True)

        await self._creator.refresh_metadata(node, element, self._address_space)

    # -------------------------------------------------------------------------
    # ConceptDescriptions
    # -------------------------------------------------------------------------

    async def _parse_concept_description_list(
        self,
        parent: INode,
        environment: Environment,
    ) -> None:
        if not environment.concept_descriptions:
            return

        for concept_description in environment.concept_descriptions:
            await self._parse_concept_description(parent, concept_description)

    async def _parse_concept_description(
        self,
        parent: INode,
        concept_description: ConceptDescription,
    ) -> None:
        logger.info(
            "aas_parser.concept_description.start",
            id_short=concept_description.id_short,
            id=concept_description.id,
        )

        await self._creator.create_concept_description(
            parent=parent,
            element=concept_description,
            address_space=self._address_space,
        )

        logger.info(
            "aas_parser.concept_description.done",
            id_short=concept_description.id_short,
        )

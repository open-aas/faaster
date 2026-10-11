from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from faaster.interfaces import INode
from faaster.interfaces.types import FaasterVariantType
from faaster.log import get_logger
from faaster.hda.buffer import AggregateBuffer
from faaster.hda.policies import AggregationPolicy

if TYPE_CHECKING:
    from faaster.extensions.method_binder import MethodBinder


logger = get_logger(__name__)


@dataclass
class NodeMetadata:
    node: INode
    path: str
    variant_type: FaasterVariantType
    id_short: str
    submodel: str
    submodel_id: str
    category: str = "VARIABLE"
    semantic_id: Optional[str] = None

    level: str = "raw"
    aggregation_policy: Optional[AggregationPolicy] = None
    buffer: AggregateBuffer = field(default_factory=AggregateBuffer)

    @property
    def has_policy(self) -> bool:
        return self.aggregation_policy is not None

    @property
    def is_virtual(self) -> bool:
        """Nós virtuais têm level diferente de raw."""
        return self.level != "raw"

    @property
    def table_suffix(self) -> str:
        """
        Sufixo para o nome da tabela TimescaleDB.
        raw   → sem sufixo
        1min  → _1min
        1hour → _1hour
        """
        if self.level == "raw":
            return ""
        return f"_{self.level}"

@dataclass
class ValueNodeEntry:
    """
    Nó OPC UA que guarda o valor vivo de um SubmodelElement,
    endereçado como na API HTTP/REST: (submodel id, idShortPath).
    """
    node: INode
    value_type: Optional[str] = None


@dataclass
class OperationEntry:
    """Operação AAS registrada durante o parser, pronta para binding."""
    id_short: str
    method_node: INode
    binder: "MethodBinder"


def _parent_path(id_short_path: str) -> str:
    return id_short_path.rsplit(".", 1)[0] if "." in id_short_path else ""


def _id_short_path(metadata: "NodeMetadata") -> str:
    # "Submodel/Coll/Prop/Value" ou ".../Value@1min" → "Coll.Prop"
    return ".".join(metadata.path.split("/")[1:-1])


def _in_subtree(path: str, root: str) -> bool:
    if not root:
        return True
    return path == root or path.startswith(f"{root}.") or path.startswith(f"{root}[")


class NodeRegistry:
    """
    Registra os nós OPC UA criados pelo parser indexados
    por node_id como chave principal.

    Índices secundários por path e semantic_id permitem
    resolução rápida pelo DriverLoader e EventBus.
    """

    def __init__(self) -> None:
        # índice principal — node_id → NodeMetadata
        self._nodes: Dict[str, NodeMetadata] = {}

        # índices secundários para resolução
        self._by_path: Dict[str, str] = {}           # path → node_id
        self._by_semantic_id: Dict[str, str] = {}    # semantic_id → node_id
        self._by_submodel: Dict[str, Dict[str, NodeMetadata]] = {}    # nodes variables dos submodels
        self._submodel_nodes: Dict[str, INode] = {}

        # operações AAS por submodelo — submodel_id_short → [OperationEntry]
        self._operations: Dict[str, List[OperationEntry]] = {}

        # mesmas operações endereçadas como na API HTTP/REST — (submodel_id, idShortPath)
        self._operations_by_path: Dict[Tuple[str, str], OperationEntry] = {}

        # nós de valor de todas as Properties — (submodel_id, idShortPath) → entry
        self._value_nodes: Dict[Tuple[str, str], ValueNodeEntry] = {}

        # nó OPC UA (Object) de cada submodelo e elemento — (submodel_id, idShortPath);
        # o próprio submodelo usa o idShortPath ""
        self._element_nodes: Dict[Tuple[str, str], INode] = {}

        self._aas_id_short: Optional[str] = None

    def register(self, metadata: NodeMetadata) -> None:
        node_id = str(metadata.node.node_id)

        self._nodes[node_id] = metadata
        self._by_path[metadata.path] = node_id

        # Value@nível compartilha o semanticId da Property: o índice aponta para o nó raw
        if metadata.semantic_id and not metadata.is_virtual:
            self._by_semantic_id[metadata.semantic_id] = node_id

        if metadata.submodel not in self._by_submodel:
            self._by_submodel[metadata.submodel] = {}
            self._by_submodel[metadata.submodel][node_id] = metadata

        else:
            self._by_submodel[metadata.submodel][node_id] = metadata

        logger.info(
            "node_registry.registered",
            node_id=node_id,
            path=metadata.path,
            id_short=metadata.id_short,
            submodel_id=metadata.submodel_id,
            semantic_id=metadata.semantic_id,
            variant_type=str(metadata.variant_type),
        )

    def set_aas_id_short(self, aas_id_short: str) -> None:
        self._aas_id_short = aas_id_short

    @property
    def aas_id_short(self) -> Optional[str]:
        """idShort da AAS raiz carregada — ex: 'AAS_STATION_MAGFRONT'."""
        return self._aas_id_short

    def register_operation(
        self,
        submodel_id_short: str,
        id_short: str,
        method_node: INode,
        binder: "MethodBinder",
        submodel_id: Optional[str] = None,
        id_short_path: Optional[str] = None,
    ) -> None:
        entry = OperationEntry(id_short=id_short, method_node=method_node, binder=binder)
        if submodel_id_short not in self._operations:
            self._operations[submodel_id_short] = []
        self._operations[submodel_id_short].append(entry)
        if submodel_id is not None and id_short_path is not None:
            self._operations_by_path[(submodel_id, id_short_path)] = entry
        logger.info(
            "node_registry.operation_registered",
            submodel=submodel_id_short,
            id_short=id_short,
        )

    def get_operations(self, submodel_id_short: str) -> List[OperationEntry]:
        return self._operations.get(submodel_id_short, [])

    def get_operation(self, submodel_id: str, id_short_path: str) -> Optional[OperationEntry]:
        return self._operations_by_path.get((submodel_id, id_short_path))

    def register_value_node(
        self,
        submodel_id: str,
        id_short_path: str,
        node: INode,
        value_type: Optional[str] = None,
    ) -> None:
        """
        Indexa o nó Value de um SubmodelElement pelo idShortPath
        (separado por pontos, relativo ao submodelo), independente da
        categoria — usado pela API HTTP/REST para ler valores vivos.
        """
        self._value_nodes[(submodel_id, id_short_path)] = ValueNodeEntry(
            node=node,
            value_type=value_type,
        )

    def get_value_node(
        self,
        submodel_id: str,
        id_short_path: str,
    ) -> Optional[ValueNodeEntry]:
        return self._value_nodes.get((submodel_id, id_short_path))

    def register_submodel_node(self, id_short, node: INode):
        self._submodel_nodes[id_short] = node

    # -------------------------------------------------------------------------
    # Nós por elemento — alterações estruturais em tempo de execução (API REST)
    # -------------------------------------------------------------------------

    def register_element_node(self, submodel_id: str, id_short_path: str, node: INode) -> None:
        self._element_nodes[(submodel_id, id_short_path)] = node

    def get_element_node(self, submodel_id: str, id_short_path: str) -> Optional[INode]:
        return self._element_nodes.get((submodel_id, id_short_path))

    def child_element_nodes(self, submodel_id: str, id_short_path: str) -> List[INode]:
        """Nós dos filhos diretos de um submodelo ("") ou coleção."""
        return [
            node
            for (sm_id, path), node in self._element_nodes.items()
            if sm_id == submodel_id and path and _parent_path(path) == id_short_path
        ]

    def runtime_value_nodes(self, submodel_id: str, id_short_path: str) -> List[INode]:
        """Nó Value (e nós virtuais Value@nível do HDA) de uma Property."""
        nodes = [
            metadata.node
            for metadata in self._nodes.values()
            if metadata.submodel_id == submodel_id and _id_short_path(metadata) == id_short_path
        ]
        entry = self._value_nodes.get((submodel_id, id_short_path))
        if entry is not None:
            nodes.append(entry.node)
        return list({node.node_id: node for node in nodes}.values())

    def nodes_in_use(self, submodel_id: str, id_short_path: str) -> List[str]:
        """
        Elementos da subárvore que o runtime usa e que, por isso, não podem ser
        removidos nem recriados: Properties historizadas/acessíveis às extensões
        (NodeMetadata) e Operations vinculadas a um método de extensão.
        """
        in_use = {
            f"{_id_short_path(metadata)} (historized)"
            for metadata in self._nodes.values()
            if metadata.submodel_id == submodel_id
            and _in_subtree(_id_short_path(metadata), id_short_path)
        }
        in_use |= {
            f"{path} (bound operation)"
            for (sm_id, path), entry in self._operations_by_path.items()
            if sm_id == submodel_id and _in_subtree(path, id_short_path) and entry.binder.is_bound
        }
        return sorted(in_use)

    def remove_subtree(self, submodel_id: str, id_short_path: str) -> None:
        """Esquece os nós da subárvore (o submodelo inteiro com idShortPath "")."""
        def inside(key: Tuple[str, str]) -> bool:
            return key[0] == submodel_id and _in_subtree(key[1], id_short_path)

        for index in (self._element_nodes, self._value_nodes):
            for key in [k for k in index if inside(k)]:
                del index[key]

        removed = {id(e) for k, e in self._operations_by_path.items() if inside(k)}
        for key in [k for k in self._operations_by_path if inside(k)]:
            del self._operations_by_path[key]
        for id_short, entries in self._operations.items():
            self._operations[id_short] = [e for e in entries if id(e) not in removed]

    def get_by_node_id(self, node_id: str) -> Optional[NodeMetadata]:
        """
        Resolução principal — usada pelo HDAManager via
        new_historized_node do asyncua.
        """
        metadata = self._nodes.get(node_id)
        if metadata is None:
            logger.warning(
                "node_registry.not_found.node_id",
                node_id=node_id,
            )

        return metadata

    def get_by_path(self, path: str) -> Optional[NodeMetadata]:
        node_id = self._by_path.get(path)
        if node_id is None:
            logger.warning(
                "node_registry.not_found.path",
                path=path,
            )
            return None

        return self._nodes.get(node_id)

    def get_by_semantic_id(self, semantic_id: str) -> Optional[NodeMetadata]:
        node_id = self._by_semantic_id.get(semantic_id)
        if node_id is None:
            logger.warning(
                "node_registry.not_found.semantic_id",
                semantic_id=semantic_id,
            )
            return None

        return self._nodes.get(node_id)

    def resolve(
        self,
        path: Optional[str] = None,
        semantic_id: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> Optional[NodeMetadata]:
        """
        Resolução com prioridade:
            1. node_id
            2. semantic_id
            3. path
        """
        if node_id:
            return self.get_by_node_id(node_id)

        if semantic_id:
            metadata = self.get_by_semantic_id(semantic_id)
            if metadata:
                return metadata

        if path:
            return self.get_by_path(path)

        return None

    def get_by_submodel(self, submodel_name: str) -> Dict[str, NodeMetadata]:
        if submodel_name not in self._by_submodel:
            logger.warning("node_registry.not_found.submodel", submodel_name=submodel_name)
            return {}

        return self._by_submodel[submodel_name]

    @property
    def all(self) -> List[NodeMetadata]:
        """Retorna todos os metadados registrados."""
        return list(self._nodes.values())

    @property
    def node_submodels(self) -> Dict[str, INode]:
        """Retorna todos os submodels registrados."""
        return self._submodel_nodes

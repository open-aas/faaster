from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from faaster.interfaces import INode
from faaster.interfaces.types import FaasterVariantType
from faaster.log import get_logger
from faaster.hda.policies import AggregationPolicy

import asyncio


logger = get_logger(__name__)


@dataclass
class AggregateBuffer:
    """
    Buffer em memória para o modo aggregate.
    Usado apenas quando AggregationPolicy.mode == aggregate.
    """
    values: List[float] = field(default_factory=list)
    window_start: Optional[datetime] = None
    task: Optional[asyncio.Task] = None

    def push(self, value: float, timestamp: datetime) -> None:
        if self.window_start is None:
            self.window_start = timestamp
        self.values.append(value)

    def flush(self) -> List[float]:
        return self.values.copy()

    def clear(self) -> None:
        self.values.clear()
        self.window_start = None

    @property
    def is_empty(self) -> bool:
        return len(self.values) == 0


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

    def register(self, metadata: NodeMetadata) -> None:
        node_id = str(metadata.node.node_id)

        self._nodes[node_id] = metadata
        self._by_path[metadata.path] = node_id

        if metadata.semantic_id:
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

    def register_submodel_node(self, id_short, node: INode):
        self._submodel_nodes[id_short] = node

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

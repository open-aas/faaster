from dataclasses import dataclass
from typing import Dict, Optional
from faaster.parser.node_registry import NodeMetadata, NodeRegistry
from faaster.interfaces import IAddressSpace, IOPCUAServer


@dataclass
class SubmodelContext:
    """
    Contexto passado para cada extensão de submódulo.

    Disponibiliza as dependências necessárias para o script
    interagir com o espaço de endereços OPC UA e o registry
    sem acoplar ao core do Faaster.
    """
    server: IOPCUAServer
    address_space: IAddressSpace
    registry: NodeRegistry
    submodel_id_short: str

    def get_node(self, path: str) -> Optional[NodeMetadata]:
        """
        Atalho para resolver um nó pelo path relativo ao submódulo.

        Exemplo:
            context.get_node("Electrical/PhaseA/Voltage/Value")
        """
        full_path = f"{self.submodel_id_short}/{path}"
        return self.registry.get_by_path(full_path)

    def get_nodes_by_semantic_id(self, semantic_id: str):
        """
        Atalho para resolver nós pelo semanticId.
        Pode retornar múltiplos — ex: Voltage em PhaseA, PhaseB, PhaseC.
        """
        return self.registry.get_by_semantic_id(semantic_id)

    @property
    def all_nodes(self) -> Dict[str, NodeMetadata]:
        """
        Todos os nós do submódulo indexados por path.
        Filtra apenas os nós que pertencem a este submódulo.
        """
        return self.registry.get_by_submodel(self.submodel_id_short)

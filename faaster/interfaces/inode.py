from abc import ABC, abstractmethod
from typing import Any, List, Optional
from .types import FaasterVariantType


class INode(ABC):
    """
    Representa um nó no espaço de endereços OPC UA.

    O script customizado do usuário manipula nós exclusivamente
    através desta interface — sem importar asyncua diretamente.
    """

    @property
    @abstractmethod
    def node_id(self) -> str:
        """Identificador único do nó no espaço de endereços."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome de navegação (BrowseName) do nó."""
        ...

    @abstractmethod
    async def get_value(self) -> Any:
        """Lê o valor atual do nó."""
        ...

    @abstractmethod
    async def set_value(
        self,
        value: Any,
        variant_type: Optional[FaasterVariantType] = None,
    ) -> None:
        """
        Atualiza o valor do nó.

        Se variant_type for None, o tipo é inferido do valor fornecido.
        """
        ...

    @abstractmethod
    async def get_parent(self) -> "INode":
        """Retorna o nó pai."""
        ...

    @abstractmethod
    async def get_children(self) -> List["INode"]:
        """Retorna todos os nós filhos."""
        ...

    @abstractmethod
    async def get_child(self, name: str) -> "INode":
        """
        Retorna um nó filho pelo nome de navegação.
        Lança NodeNotFoundError se não encontrado.
        """
        ...

    @abstractmethod
    async def read_data_value(self) -> Any:
        """
        Lê o DataValue completo do nó, incluindo
        valor, tipo, timestamp e status code.
        """
        ...

    @abstractmethod
    async def write_data_value(self, data_value: Any) -> None:
        """
        Escreve um DataValue completo no nó, incluindo
        timestamp de origem (SourceTimestamp).
        """
        ...

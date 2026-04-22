from abc import abstractmethod, ABC
from typing import Optional, Any, List, Callable
from .types import FaasterVariantType, MethodArgument, FaasterLocalizedText
from .inode import INode


class IAddressSpace(ABC):
    """
    Interface para operações no espaço de endereços OPC UA.

    Recebida pelo IElementCreator e pelo script customizado
    do usuário — sem acesso direto ao asyncua.
    """

    @abstractmethod
    async def get_objects_node(self) -> INode:
        ...

    @abstractmethod
    async def get_node(self, node_id: str) -> INode:
        ...

    @abstractmethod
    def set_namespace(self, uri: str) -> None:
        ...

    @abstractmethod
    async def get_namespace_index(self, uri: str) -> int:
        ...

    @abstractmethod
    async def add_folder(
        self,
        parent: INode,
        name: str,
    ) -> INode:
        ...

    @abstractmethod
    async def add_object(
        self,
        parent: INode,
        name: str,
        object_type_id: Optional[str] = None,
    ) -> INode:
        ...

    @abstractmethod
    async def add_property(
        self,
        parent: INode,
        name: str,
        value: Any,
        variant_type: Optional[FaasterVariantType] = None,
    ) -> INode:
        ...

    @abstractmethod
    async def add_method(
        self,
        parent: INode,
        name: str,
        callback: Callable,
        input_args: Optional[List[MethodArgument]] = None,
        output_args: Optional[List[MethodArgument]] = None,
    ) -> INode:
        ...

    @abstractmethod
    async def set_value(
        self,
        node: INode,
        value: Any,
        variant_type: Optional[FaasterVariantType] = None,
        source_timestamp: Optional[Any] = None,
    ) -> None:
        ...

    @abstractmethod
    async def get_value(self, node: INode) -> Any:
        ...

    @abstractmethod
    async def add_variable(
            self,
            parent: INode,
            name: str,
            value: Any,
            variant_type: Optional[FaasterVariantType] = None,
            writable: bool = False,
            is_array: bool = False,
    ) -> INode:
        """
        Adiciona uma variável ao pai fornecido.

        Se is_array=True, o valor deve ser uma lista e o
        ValueRank será definido como unidimensional.
        Se writable=True, define AccessLevel como read+write.
        """
        ...

    @abstractmethod
    async def set_display_name(
            self,
            node: INode,
            value: FaasterLocalizedText,
    ) -> None:
        """
        Seta o atributo DisplayName nativo do nó OPC UA
        com o primeiro item da lista display_name do metamodelo.
        """
        ...

    @abstractmethod
    async def set_description(
            self,
            node: INode,
            value: FaasterLocalizedText,
    ) -> None:
        """
        Seta o atributo Description nativo do nó OPC UA
        com o primeiro item da lista description do metamodelo.
        """
        ...

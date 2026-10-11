from abc import abstractmethod, ABC
from typing import Any, Optional
from .inode import INode
from .iaddress_space import IAddressSpace


class IElementCreator(ABC):
    """
    Interface que define como cada elemento do metamodelo AAS V3
    é traduzido para nós OPC UA.
    """

    @abstractmethod
    async def create_aas(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
    ) -> INode:
        ...

    @abstractmethod
    async def create_submodel(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
    ) -> INode:
        ...

    @abstractmethod
    async def create_property(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        ...

    @abstractmethod
    async def create_operation(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        ...

    @abstractmethod
    async def create_submodel_element_collection(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        ...

    @abstractmethod
    async def create_range(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        ...

    @abstractmethod
    async def create_multi_language_property(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        ...

    @abstractmethod
    async def create_reference_element(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        ...

    @abstractmethod
    async def create_file(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        ...

    @abstractmethod
    async def create_basic_event_element(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        ...

    async def create_submodel_element_list(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        """SubmodelElementList (só o nó da lista; os itens são criados pelo parser)."""
        raise NotImplementedError

    async def create_entity(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        """Entity (só o nó da entidade; os statements são criados pelo parser)."""
        raise NotImplementedError

    async def create_relationship_element(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        """RelationshipElement e AnnotatedRelationshipElement (as annotations são criadas pelo parser)."""
        raise NotImplementedError

    async def create_capability(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        """Capability."""
        raise NotImplementedError

    async def create_blob(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        """Blob."""
        raise NotImplementedError

    async def refresh_metadata(
        self,
        node: INode,
        element: Any,
        address_space: IAddressSpace,
    ) -> None:
        """
        Recria os nós de metadados (IdShort, Description, SemanticId...) de um
        elemento já existente, sem tocar nos filhos nem no nó de valor.
        Os nós de metadados antigos já devem ter sido removidos.
        """
        raise NotImplementedError

from abc import abstractmethod, ABC
from typing import Any
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
    ) -> INode:
        ...

    @abstractmethod
    async def create_operation(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
    ) -> INode:
        ...

    @abstractmethod
    async def create_submodel_element_collection(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
    ) -> INode:
        ...

    @abstractmethod
    async def create_range(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
    ) -> INode:
        ...

    @abstractmethod
    async def create_multi_language_property(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
    ) -> INode:
        ...

    @abstractmethod
    async def create_reference_element(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
    ) -> INode:
        ...

    @abstractmethod
    async def create_file(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
    ) -> INode:
        ...

    @abstractmethod
    async def create_basic_event_element(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
    ) -> INode:
        ...

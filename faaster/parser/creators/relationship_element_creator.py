from typing import Optional, Union
from faaster.interfaces import IAddressSpace, INode
from faaster.aas_metamodel.models.relationship_element import RelationshipElement
from faaster.aas_metamodel.models.annotated_relationship_element import AnnotatedRelationshipElement
from .base import BaseCreator
from faaster.log import get_logger


logger = get_logger(__name__)


class RelationshipElementCreator(BaseCreator):
    """
    RelationshipElement e AnnotatedRelationshipElement: Object com as
    referências First e Second. As annotations são criadas pelo parser como
    filhos deste nó.
    """

    async def create(
        self,
        parent: INode,
        element: Union[RelationshipElement, AnnotatedRelationshipElement],
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        name = name or element.id_short or "RelationshipElement"
        node = await address_space.add_object(parent, name)
        await self.add_metadata(node, element, address_space)
        return node

    async def add_metadata(
        self,
        node: INode,
        element: Union[RelationshipElement, AnnotatedRelationshipElement],
        address_space: IAddressSpace,
    ) -> None:
        await self.add_id_short(node, element, address_space)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "Category", element.category)

        await self.add_reference(node, "First", element.first, address_space)
        await self.add_reference(node, "Second", element.second, address_space)

        if element.semantic_id:
            await self.add_semantic_id(node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

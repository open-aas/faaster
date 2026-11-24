from faaster.interfaces import IAddressSpace, INode
from .base import BaseCreator
from faaster.log import get_logger


logger = get_logger(__name__)


class SubmodelElementListCreator(BaseCreator):
    """SubmodelElementList → Object; its items are parsed as children named ``[i]`` by the parser."""

    async def create(self, parent: INode, element, address_space: IAddressSpace) -> INode:
        name = element.id_short or "SubmodelElementList"
        node = await address_space.add_object(parent, name)

        await address_space.add_property(node, "IdShort", name)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "Category", element.category)
        await address_space.add_property(node, "OrderRelevant", element.order_relevant)
        await address_space.add_property(
            node, "TypeValueListElement", getattr(element.type_value_list_element, "value",
                                                  element.type_value_list_element)
        )
        if element.value_type_list_element:
            await address_space.add_property(
                node, "ValueTypeListElement", getattr(element.value_type_list_element, "value",
                                                      element.value_type_list_element)
            )
        await self.add_reference(node, "SemanticIdListElement", element.semantic_id_list_element,
                                 address_space)

        if element.semantic_id:
            await self.add_semantic_id(node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

        return node

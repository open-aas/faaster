from faaster.interfaces import IAddressSpace, INode
from .base import BaseCreator
from faaster.log import get_logger


logger = get_logger(__name__)


class CapabilityCreator(BaseCreator):
    """Capability → Object with the metadata only (a capability has no value)."""

    async def create(self, parent: INode, element, address_space: IAddressSpace) -> INode:
        name = element.id_short or "Capability"
        node = await address_space.add_object(parent, name)

        await address_space.add_property(node, "IdShort", name)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "Category", element.category)

        if element.semantic_id:
            await self.add_semantic_id(node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

        return node

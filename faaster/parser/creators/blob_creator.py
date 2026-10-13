from faaster.interfaces import IAddressSpace, INode
from .base import BaseCreator
from faaster.log import get_logger


logger = get_logger(__name__)


class BlobCreator(BaseCreator):
    """Blob → Object with ``ContentType`` and ``Value`` (the base64 text of the model)."""

    async def create(self, parent: INode, element, address_space: IAddressSpace) -> INode:
        name = element.id_short or "Blob"
        node = await address_space.add_object(parent, name)

        await address_space.add_property(node, "IdShort", name)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "Category", element.category)
        await address_space.add_property(node, "ContentType", element.content_type or "")
        await address_space.add_property(node, "Value", element.value or "")

        if element.semantic_id:
            await self.add_semantic_id(node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

        return node

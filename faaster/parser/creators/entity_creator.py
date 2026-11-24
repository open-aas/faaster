from faaster.interfaces import IAddressSpace, INode
from .base import BaseCreator
from faaster.log import get_logger


logger = get_logger(__name__)


class EntityCreator(BaseCreator):
    """Entity → Object; its statements are parsed as children by the parser."""

    async def create(self, parent: INode, element, address_space: IAddressSpace) -> INode:
        name = element.id_short or "Entity"
        node = await address_space.add_object(parent, name)

        await address_space.add_property(node, "IdShort", name)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "Category", element.category)
        await address_space.add_property(
            node, "EntityType", getattr(element.entity_type, "value", element.entity_type)
        )
        if element.global_asset_id:
            await address_space.add_property(node, "GlobalAssetId", element.global_asset_id)
        if element.specific_asset_ids:
            folder = await address_space.add_folder(node, "SpecificAssetIds")
            for asset_id in element.specific_asset_ids:
                await address_space.add_property(folder, asset_id.name, asset_id.value)

        if element.semantic_id:
            await self.add_semantic_id(node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

        return node

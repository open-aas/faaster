from typing import Optional
from faaster.interfaces import IAddressSpace, INode
from faaster.aas_metamodel.models.entity import Entity
from .base import BaseCreator, _enum_value
from faaster.log import get_logger


logger = get_logger(__name__)


class EntityCreator(BaseCreator):
    """
    Object da entidade com seus metadados. Os statements são criados pelo
    parser como filhos deste nó, como os elementos de uma coleção.
    """

    async def create(
        self,
        parent: INode,
        element: Entity,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        name = name or element.id_short or "Entity"
        node = await address_space.add_object(parent, name)
        await self.add_metadata(node, element, address_space)
        return node

    async def add_metadata(
        self,
        node: INode,
        element: Entity,
        address_space: IAddressSpace,
    ) -> None:
        await self.add_id_short(node, element, address_space)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "Category", element.category)

        if element.entity_type:
            await address_space.add_property(node, "EntityType", _enum_value(element.entity_type))

        if element.global_asset_id:
            await address_space.add_property(node, "GlobalAssetId", element.global_asset_id)

        if element.specific_asset_ids:
            folder = await address_space.add_folder(node, "SpecificAssetIds")
            for specific_asset_id in element.specific_asset_ids:
                await address_space.add_property(folder, specific_asset_id.name, specific_asset_id.value)

        if element.semantic_id:
            await self.add_semantic_id(node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

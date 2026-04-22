from faaster.interfaces import IAddressSpace, INode
from faaster.aas_metamodel.models.submodel_element_collection import SubmodelElementCollection
from .base import BaseCreator
from faaster.log import get_logger


logger = get_logger(__name__)


class CollectionCreator(BaseCreator):

    async def create(
        self,
        parent: INode,
        element: SubmodelElementCollection,
        address_space: IAddressSpace,
    ) -> INode:
        name = element.id_short or "Collection"
        node = await address_space.add_object(parent, name)

        await address_space.add_property(node, "IdShort", name)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "Category", element.category)

        if element.semantic_id:
            await self.add_semantic_id(node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

        return node

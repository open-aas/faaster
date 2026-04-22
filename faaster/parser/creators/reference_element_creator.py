from faaster.interfaces import IAddressSpace, INode
from faaster.aas_metamodel.models.reference_element import ReferenceElement
from .base import BaseCreator
from faaster.log import get_logger


logger = get_logger(__name__)


class ReferenceElementCreator(BaseCreator):

    async def create(
        self,
        parent: INode,
        element: ReferenceElement,
        address_space: IAddressSpace,
    ) -> INode:
        name = element.id_short or "ReferenceElement"
        node = await address_space.add_object(parent, name)

        await address_space.add_property(node, "IdShort", name)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "Category", element.category)

        if element.value and element.value.keys:
            keys_folder = await address_space.add_folder(node, "Keys")
            for i, key in enumerate(element.value.keys):
                await address_space.add_property(
                    keys_folder,
                    f"Key[{i}]@{key.type.value}",
                    key.value,
                )

        if element.semantic_id:
            await self.add_semantic_id(node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

        return node

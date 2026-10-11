from typing import Optional
from faaster.interfaces import IAddressSpace, INode
from faaster.interfaces.types import FaasterVariantType
from faaster.aas_metamodel.models.file import File
from .base import BaseCreator
from faaster.log import get_logger


logger = get_logger(__name__)


class FileCreator(BaseCreator):

    async def create(
        self,
        parent: INode,
        element: File,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        name = name or element.id_short or "File"

        node = await address_space.add_object(parent, name)

        await self.add_id_short(node, element, address_space)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "Category", element.category)
        await address_space.add_property(node, "ContentType", element.content_type)

        await address_space.add_variable(
            parent=node,
            name="Value",
            value=element.value or "",
            variant_type=FaasterVariantType.String,
        )

        if element.semantic_id:
            await self.add_semantic_id(node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

        return node

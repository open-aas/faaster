from typing import Optional
from faaster.interfaces import IAddressSpace, INode
from faaster.aas_metamodel.models.multi_language_property import MultiLanguageProperty
from .base import BaseCreator
from faaster.log import get_logger


logger = get_logger(__name__)


class MultiLanguagePropertyCreator(BaseCreator):

    async def create(
        self,
        parent: INode,
        element: MultiLanguageProperty,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        name = name or element.id_short or "MultiLanguageProperty"
        node = await address_space.add_object(parent, name)

        await self.add_id_short(node, element, address_space)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "Category", element.category)

        if element.value:
            for display_name in element.value:
                lang = display_name.language or "und"
                text = display_name.text or ""
                await address_space.add_property(node, lang, text)

        if element.semantic_id:
            await self.add_semantic_id(node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

        return node
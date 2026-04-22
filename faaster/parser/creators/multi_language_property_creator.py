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
    ) -> INode:
        name = element.id_short or "MultiLanguageProperty"
        node = await address_space.add_object(parent, name)

        await address_space.add_property(node, IdShort, name)
        await address_space.add_property(node, "ModelType", element.modelType)
        await address_space.add_property(node, "Category", element.category)

        if element.value:
            for display_name in element.value:
                lang = display_name.language or "und"
                text = display_name.text or ""
                await address_space.add_property(node, lang, text)

        if element.semanticId:
            await self.add_semantic_id(node, element.semanticId, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

        return node
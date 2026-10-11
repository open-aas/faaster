from typing import Optional
from faaster.interfaces import IAddressSpace, INode
from faaster.aas_metamodel.models.submodel_element_list import SubmodelElementList
from .base import BaseCreator, _enum_value
from faaster.log import get_logger


logger = get_logger(__name__)


class SubmodelElementListCreator(BaseCreator):
    """
    Object da lista com seus metadados. Os itens são criados pelo parser
    como filhos deste nó, nomeados pelo índice ("[0]", "[1]"...).
    """

    async def create(
        self,
        parent: INode,
        element: SubmodelElementList,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        name = name or element.id_short or "SubmodelElementList"
        node = await address_space.add_object(parent, name)
        await self.add_metadata(node, element, address_space)
        return node

    async def add_metadata(
        self,
        node: INode,
        element: SubmodelElementList,
        address_space: IAddressSpace,
    ) -> None:
        await self.add_id_short(node, element, address_space)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "Category", element.category)
        # orderRelevant ausente = true (Part 1)
        await address_space.add_property(
            node, "OrderRelevant", element.order_relevant if element.order_relevant is not None else True
        )
        await address_space.add_property(
            node, "TypeValueListElement", _enum_value(element.type_value_list_element)
        )

        if element.value_type_list_element:
            await address_space.add_property(
                node, "ValueTypeListElement", _enum_value(element.value_type_list_element)
            )

        if element.semantic_id_list_element:
            await self.add_reference(
                node, "SemanticIdListElement", element.semantic_id_list_element, address_space
            )

        if element.semantic_id:
            await self.add_semantic_id(node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

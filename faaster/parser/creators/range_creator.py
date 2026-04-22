from faaster.interfaces import IAddressSpace, INode
from faaster.aas_metamodel.models.range import Range
from .base import BaseCreator, resolve_variant_type, cast_value
from faaster.log import get_logger


logger = get_logger(__name__)


class RangeCreator(BaseCreator):

    async def create(
        self,
        parent: INode,
        element: Range,
        address_space: IAddressSpace,
    ) -> INode:
        name = element.id_short or "Range"
        node = await address_space.add_object(parent, name)

        variant_type = resolve_variant_type(element.value_type)

        await address_space.add_variable(
            parent=node,
            name="Min",
            value=cast_value(element.min, variant_type),
            variant_type=variant_type,
        )
        await address_space.add_variable(
            parent=node,
            name="Max",
            value=cast_value(element.max, variant_type),
            variant_type=variant_type,
        )

        await address_space.add_property(node, "IdShort", name)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "ValueType", element.value_type)

        if element.semantic_id:
            await self.add_semantic_id(node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

        return node

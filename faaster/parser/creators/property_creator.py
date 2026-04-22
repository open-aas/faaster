from typing import List, Any, Optional, Tuple
from faaster.interfaces import IAddressSpace, INode
from faaster.aas_metamodel.models.property import Property
from faaster.interfaces.types import FaasterVariantType
from faaster.hda import HDAMode, extract_policy, AggregationPolicy
from faaster.log import get_logger
from .base import BaseCreator, resolve_variant_type, cast_value


logger = get_logger(__name__)


class PropertyCreator(BaseCreator):

    async def create(
        self,
        parent: INode,
        element: Property,
        address_space: IAddressSpace,
    ) -> INode:
        name = element.id_short or "Property"
        prop_node = await address_space.add_object(parent, name)

        variant_type = resolve_variant_type(element.value_type)
        casted_value = cast_value(element.value, variant_type)

        # retornamos o value_node — é ele que o HDA historiza
        value_node = await address_space.add_variable(
            parent=prop_node,
            name="Value",
            value=casted_value,
            variant_type=variant_type
        )

        await address_space.add_property(prop_node, "IdShort", name)
        await address_space.add_property(prop_node, "Category", element.category)
        await address_space.add_property(prop_node, "ModelType", element.type_model)
        await address_space.add_property(prop_node, "ValueType", element.value_type)

        if element.semantic_id:
            await self.add_semantic_id(prop_node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(prop_node, element.description, address_space)

        return value_node

    @staticmethod
    async def _create_virtual_nodes(
        parent: INode,
        levels: List[str],
        value: Any,
        variant_type: FaasterVariantType,
        address_space: IAddressSpace,
    ) -> List[INode]:
        nodes = []
        for level in levels:
            node = await address_space.add_variable(
                parent=parent,
                name=f"Value@{level}",
                value=value,
                variant_type=variant_type,
                writable=False,
            )

            nodes.append(node)

        return nodes

    @staticmethod
    async def create_virtual_nodes(
        parent: INode,
        element: Property,
        address_space: IAddressSpace,
    ) -> Tuple[List[Tuple[INode, str]], Optional[AggregationPolicy]]:
        is_variable = element.category == "VARIABLE"
        policy = extract_policy(element.extensions)
        variant_type = resolve_variant_type(element.value_type)
        casted_value = cast_value(element.value, variant_type)
        result: List[Tuple[INode,  str]] = []

        if is_variable and policy is not None and policy.is_sample:
            for level in policy.levels:
                node = await address_space.add_variable(
                    parent=parent,
                    name=f"Value@{level}",
                    value=casted_value,
                    variant_type=variant_type,
                    writable=False,
                )
                result.append((node, level))

        return result, policy

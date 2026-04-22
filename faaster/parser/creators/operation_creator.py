from faaster.interfaces import IAddressSpace, INode
from faaster.interfaces.types import MethodArgument
from faaster.aas_metamodel.models.operation import Operation
from .base import BaseCreator, resolve_variant_type
from faaster.log import get_logger


logger = get_logger(__name__)


class OperationCreator(BaseCreator):

    async def create(
        self,
        parent: INode,
        element: Operation,
        address_space: IAddressSpace,
    ) -> INode:
        name = element.id_short or "Operation"
        op_node = await address_space.add_object(parent, name)

        await address_space.add_property(op_node, IdShort, name)
        await address_space.add_property(op_node, "ModelType", element.modelType)

        async def _placeholder_callback(*args):
            ...

        input_args = [
            MethodArgument(
                name=var.value.id_short or "input",
                variant_type=resolve_variant_type(var.value.valueType),
                description=f"Input: {var.value.id_short}",
            )
            for var in (element.inputVariables or [])
            if var.value
        ]

        output_args = [
            MethodArgument(
                name=var.value.id_short or "output",
                variant_type=resolve_variant_type(var.value.valueType),
                description=f"Output: {var.value.id_short}",
            )
            for var in (element.outputVariables or [])
            if var.value
        ]

        await address_space.add_method(
            parent=op_node,
            name=name,
            callback=_placeholder_callback,
            input_args=input_args,
            output_args=output_args,
        )

        return op_node

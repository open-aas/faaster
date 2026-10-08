from faaster.interfaces import IAddressSpace, INode
from faaster.interfaces.types import MethodArgument
from faaster.aas_metamodel.models.operation import Operation
from faaster.extensions.method_binder import MethodBinder
from .base import BaseCreator, resolve_variant_type
from faaster.log import get_logger


logger = get_logger(__name__)


class OperationCreator(BaseCreator):

    async def create(
        self,
        parent: INode,
        element: Operation,
        address_space: IAddressSpace,
    ) -> tuple[INode, MethodBinder]:
        name = element.id_short or "Operation"
        op_node = await address_space.add_object(parent, name)

        await address_space.add_property(op_node, "IdShort", name)
        await address_space.add_property(op_node, "ModelType", element.type_model)

        binder = MethodBinder()

        input_args = [
            MethodArgument(
                name=var.value.get("idShort") or "input",
                variant_type=resolve_variant_type(var.value.get("valueType")),
                description=f"Input: {var.value.get('idShort')}",
            )
            for var in (element.input_variables or [])
            if var.value
        ]

        output_args = [
            MethodArgument(
                name=var.value.get("idShort") or "output",
                variant_type=resolve_variant_type(var.value.get("valueType")),
                description=f"Output: {var.value.get('idShort')}",
            )
            for var in (element.output_variables or [])
            if var.value
        ]

        method_node = await address_space.add_method(
            parent=op_node,
            name=name,
            callback=binder,
            input_args=input_args,
            output_args=output_args,
        )

        logger.info(
            "operation_creator.created",
            name=name,
            input_count=len(input_args),
            output_count=len(output_args),
        )

        return method_node, binder

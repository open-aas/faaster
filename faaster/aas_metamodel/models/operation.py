"""An operation is a submodel element with input and output variables."""

# pylint: disable=duplicate-code

from typing import List, Literal, Optional
from pydantic import Field, model_validator
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.operation_variable import OperationVariable
from faaster.aas_metamodel.models.submodel_element import SubmodelElement
from faaster.aas_metamodel.exceptions import InvalidFieldException


class Operation(SubmodelElement):
    """An operation is a submodel element with input and output variables.

    :param input_variables: Input parameter of the operation.
    :param output_variables: Output parameter of the operation.
    :param inoutput_variables: Parameter that is input and output of the operation.
    """

    type_model: Literal[ModelType.OPERATION] = Field(alias="modelType", default=ModelType.OPERATION)
    input_variables: Optional[List[OperationVariable]] = []
    output_variables: Optional[List[OperationVariable]] = []
    inoutput_variables: Optional[List[OperationVariable]] = []

    def __init__(
        self,
        input_variables: Optional[List[dict]] = None,
        output_variables: Optional[List[dict]] = None,
        inoutput_variables: Optional[List[dict]] = None,
        **attrs,
    ):
        """Initialize an Operation with its input, output, and inoutput variables.

        :param self: Instance of Operation.
        :param input_variables: List of input variable dictionaries.
        :param output_variables: List of output variable dictionaries.
        :param inoutput_variables: List of inoutput variable dictionaries.
        :param attrs: Additional attributes for the Operation.
        :return: None
        """
        attrs["input_variables"] = self.initialize_variables(input_variables)
        attrs["output_variables"] = self.initialize_variables(output_variables)
        attrs["inoutput_variables"] = self.initialize_variables(inoutput_variables)

        super().__init__(**attrs)

    @staticmethod
    def initialize_variables(
        variables: Optional[List[dict]],
    ) -> List[OperationVariable]:
        """Convert variable dictionaries into OperationVariable instances.

        :param variables: List of variable dictionaries.
        :return: List of initialized OperationVariable objects.
        """
        initialized_variables = []
        if variables:
            for var_data in variables:
                value = var_data.pop("value", None)
                initialized_variables.append(OperationVariable(value=value, **var_data))
        return initialized_variables

    @model_validator(mode="after")
    def validate_unique_variables_id_shorts(self) -> "Operation":
        """Constraint AASd-134.

        For an Operation, the idShort of all inputVariable/value,
        outputVariable/value, and inoutputVariable/value shall be unique.
        """
        id_short_set = set()
        all_variables = (
            (self.input_variables or [])
            + (self.output_variables or [])
            + (self.inoutput_variables or [])
        )

        for var in all_variables:
            if not var.value:
                continue

            id_short = var.value.get("idShort") or var.value.get("id_short")
            if not id_short:
                continue

            if id_short in id_short_set:
                raise InvalidFieldException(
                    detail=f"Duplicate idShort '{id_short}' found in operation variables. "
                    "The idShort of all variable values must be unique (AASd-134)."
                )
            id_short_set.add(id_short)

        return self

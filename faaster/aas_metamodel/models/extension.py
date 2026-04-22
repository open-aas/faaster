"""Single extension of an element."""

from typing import List, Optional
from pydantic import field_validator, model_validator
from faaster.aas_metamodel.models.data_type_def_xsd import DataTypeDefXsd
from faaster.aas_metamodel.models.has_semantics import HasSemantics
from faaster.aas_metamodel.models.reference import Reference
from faaster.aas_metamodel.models.reference_types import ReferenceTypes
from faaster.aas_metamodel.models.value_data_type import ValueDataType
from faaster.aas_metamodel.exceptions import InvalidFieldException
from faaster.aas_metamodel.validators import validate_value_type


class Extension(HasSemantics):
    """Single extension of an element.

    :param name: An extension of an element.
    The name of an extension within HasExtensions needs to be unique.
    :param value_type: Type of the value of the extension. Default: xsd:string
    :param value: Value of the extension
    :param refers_to: Reference to an element the extension refers to.
    """

    name: str
    value_type: Optional[DataTypeDefXsd] = DataTypeDefXsd.STRING
    value: Optional[ValueDataType] = None
    refers_to: Optional[List[Reference]] = []

    @field_validator("refers_to", mode="after")
    @classmethod
    def validate_refers_to(cls, value):
        """Ensure that all items in 'refers_to' are of type ModelReference.

        :param cls: The model class where the validator is applied.
        :param value: List of Reference objects in 'refers_to'.
        :return: The validated list of Reference objects.
        :raises InvalidFieldException: If any reference is not a ModelReference.
        """
        if value:
            for reference in value:
                if reference.type != ReferenceTypes.MODEL_REFERENCE:
                    raise InvalidFieldException(
                        detail="The 'extensions/refersTo' field must be of type 'ModelReference'."
                    )

        return value

    @model_validator(mode="before")
    @classmethod
    def check_value_type(cls, values):
        """Validate that the provided 'value' matches the declared 'valueType'.

        :param cls: The model class where the validator is applied.
        :param values: Dictionary of field values for model initialization.
        :return: The validated dictionary of field values.
        """
        if "valueType" in values:
            modified_value = values.get("value")
            value_type_str = values.get("valueType")

            if modified_value is not None:
                validate_value_type(modified_value, value_type_str)

        return values

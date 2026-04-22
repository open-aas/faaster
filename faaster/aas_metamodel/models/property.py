"""A property is a data element that has a single value."""

# pylint: disable=duplicate-code

from typing import Literal, Optional
from pydantic import Field, model_validator
from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.models.data_element import DataElement
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.reference import Reference
from faaster.aas_metamodel.models.value_data_type import ValueDataType
from faaster.aas_metamodel.validators import validate_value_type


class Property(DataElement):
    """A property is a data element that has a single value.

    :param value_type: Data type of the value.
    :param value: The value of the property instance.
    :param value_id: Reference to the global unique ID of a coded value.
    """

    type_model: Literal[ModelType.PROPERTY] = Field(alias="modelType", default=ModelType.PROPERTY)
    value_type: ConstrainedString = Field(default="xs:int")
    value: Optional[ValueDataType] = None
    value_id: Optional[Reference] = None

    @model_validator(mode="before")
    @classmethod
    def check_value_type(cls, values):
        """Ensure that the field 'value' matches the declared 'valueType'.

        :param cls: The model class where the validator is applied.
        :param values: Dictionary of incoming field values.
        :return: The validated dictionary of field values.
        """
        if "valueType" in values:
            modified_value = values.get("value")
            value_type_str = values.get("valueType")

            if modified_value is not None:
                validate_value_type(modified_value, value_type_str)

        return values

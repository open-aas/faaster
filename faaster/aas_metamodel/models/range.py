"""A range data element is a data element that defines a range with min and max."""

from typing import Literal, Optional
from pydantic import Field
from faaster.aas_metamodel.models.data_element import DataElement
from faaster.aas_metamodel.models.data_type_def_xsd import DataTypeDefXsd
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.value_data_type import ValueDataType


class Range(DataElement):
    """A range data element is a data element that defines a range with min and max.

    :param value_type: Data type of the min and max.
    :param min: The minimum value of the range. If the min value is missing,
    then the value is assumed to be negative infinite.
    :param max: The maximum value of the range. If the max value is missing,
    then the value is assumed to be positive infinite.
    """

    type_model: Literal[ModelType.RANGE] = Field(alias="modelType", default=ModelType.RANGE)
    value_type: DataTypeDefXsd
    min: Optional[ValueDataType] = None
    max: Optional[ValueDataType] = None

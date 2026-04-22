"""Represents a value with any XSD atomic type as specified via DataTypeDefXsd."""

from typing import Union
from faaster.aas_metamodel.models.constrained_string import ConstrainedString

# Represents a value with any XSD atomic type as specified via DataTypeDefXsd.
ValueDataType = Union[int, float, bool, bytes, ConstrainedString]

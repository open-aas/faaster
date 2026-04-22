"""Represents an identifier string that distinguishes one entity from another in a given domain."""

from typing import Union
from pydantic import UUID4, AnyUrl
from faaster.aas_metamodel.models.constrained_string import ConstrainedString

# Represents an identifier string that distinguishes one entity from another in a given domain.
Identifier = Union[AnyUrl, UUID4, ConstrainedString]

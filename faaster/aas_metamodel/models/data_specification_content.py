"""Data specification content of an element."""

from typing import Optional
from pydantic import Field
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.constrained_string import ConstrainedString


class DataSpecificationContent(DTO):
    """Data specification content of an element.

    Data specification content is part of a data specification template and defines which
    additional attributes shall be added to the element instance that references the data
    specification template and meta information about the template itself.
    """

    type_model: Optional[ConstrainedString] = Field(None, alias="modelType")

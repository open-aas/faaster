"""An element that is referable by its idShort (for descriptors)."""

# pylint: disable=duplicate-code

from typing import List, Optional
from pydantic import Field, field_validator
from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.models.has_extensions import HasExtensions
from faaster.aas_metamodel.models.lang_string_set import LangStringSet
from faaster.aas_metamodel.exceptions import InvalidFieldException

import re


class ReferableDescriptor(HasExtensions):
    """An element that is referable by its idShort (for descriptors).

    This ID is not globally unique.
    """

    id_short: Optional[ConstrainedString] = Field(None, max_length=128)
    display_name: Optional[List[LangStringSet]] = []
    description: Optional[List[LangStringSet]] = []

    @field_validator("id_short")
    @classmethod
    def validate_id_short(cls, value):
        """Constraint AASd-002.

        The idShort of Referables shall only feature letters, digits, underscore ("_");
        starting mandatory with a letter, i.e. [a-zA-Z][a-zA-Z0-9_]*.
        """
        if value is None:
            return value

        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", value):
            raise InvalidFieldException(
                detail=f"Invalid idShort value: '{value}'. "
                "The idShort must begin with a letter and may only contain letters, digits, "
                "or underscores (Constraint AASd-002)."
            )
        return value

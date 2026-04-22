"""This module defines a constrained string type based on the AASd-130 constraint."""

from typing import Annotated
from pydantic import StringConstraints, field_validator
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.exceptions import InvalidFieldException

import re


AASD_130_REGEX = r"^[\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\u10000-\u10FFFF]*$"
ConstrainedString = Annotated[str, StringConstraints(pattern=AASD_130_REGEX)]


class ExampleModel(DTO):
    """This module defines a constrained string type based on the AASd-130 constraint.

    Constraint AASd-130 states:
    - An attribute with data type "string" shall consist of the following characters only:
      ^[\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\u00010000-\u0010FFFF]*$

    The purpose of this module is to enforce this constraint in a reusable and
    centralized manner using Pydantic `StringConstraints`.
    """

    field: ConstrainedString

    @field_validator("field", mode="before")
    @classmethod
    def validate_field(cls, value: str) -> str:
        """Validate that the field complies with the AASd-130 constraint pattern.

        :param value: Field value to validate.
        :return: The validated field value.
        :raises InvalidFieldException: If the value does not match the required pattern.
        """
        if not re.match(AASD_130_REGEX, value):
            raise InvalidFieldException(detail="Field must follow the AASd-130 constraint pattern.")
        return value

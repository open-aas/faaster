"""An element that is referable by its idShort. This ID is not globally unique."""

# pylint: disable=duplicate-code

from typing import List, Optional
from pydantic import Field, field_validator
from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.models.has_extensions import HasExtensions
from faaster.aas_metamodel.models.lang_string_set import LangStringSet
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.exceptions import InvalidFieldException

import re


class Referable(HasExtensions):
    """An element that is referable by its idShort. This ID is not globally unique.

    This ID is unique withing the name space of the element.

    :param category: The category is a value that gives further meta information w.r.t.
    the class of the element.
    It affects the expected existence of attributes and the applicability of constraints.
    :param id_short: In case of identifiables this attribute is a short name of the element.
    In case of referable this ID is an identifying string of the element within its name space.
    :param display_name: Can be provided in several languages.
    :param description: Description or comments on the element.
    The description can be provided in several languages.
    :param type_model: The type of model element.
    """

    category: Optional[ConstrainedString] = None
    id_short: Optional[ConstrainedString] = Field(None, max_length=128)
    display_name: Optional[List[LangStringSet]] = []
    description: Optional[List[LangStringSet]] = []
    type_model: ModelType = Field(alias="modelType")

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

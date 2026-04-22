"""Represents a language-tagged string in the format "text@language"."""

from pydantic import Field
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.constrained_string import ConstrainedString


class LangString(DTO):
    """Represents a language-tagged string in the format "text@language".

    :param language: The language code.
    :param text: The text value.
    """

    language: ConstrainedString = Field(...)
    text: ConstrainedString = Field(...)

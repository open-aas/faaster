"""Array of elements of type LangString."""

from pydantic import Field, field_validator
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.exceptions import InvalidFieldException

import structlog
import pycountry


logger = structlog.get_logger(__name__)


class LangStringSet(DTO):
    """Array of elements of type LangString.

    :param language: The language code.
    :param text: The text value.
    """

    language: ConstrainedString = Field(...)
    text: ConstrainedString = Field(...)

    @field_validator("language")
    @classmethod
    def validate_language(cls, value):
        """Validate that the language code follows ISO 639-1 format.

        :param cls: The model class where the validator is applied.
        :param value: The language tag string (e.g., 'pt-BR').
        :return: The validated language tag.
        """
        if value:
            lang_code = value.split("-")[0]
            if not value.split("-")[0].islower():
                logger.error(f"Invalid language code format: {value}")
                raise InvalidFieldException(
                    detail=f"The language code of the language tag must consist of exactly two "
                    f"lower-case letters! Given language code: {value.split('-')[0]}"
                )

            # Exception to "jp"
            if lang_code in ["jp", "cn"]:
                return value

            if not pycountry.languages.get(alpha_2=lang_code):
                logger.error(f"Invalid language code: {value}")
                raise InvalidFieldException(
                    detail=f"Invalid language code '{value}'. "
                    "Ensure the language is provided in a valid format, such as 'pt-BR' or "
                    "'de-CH'. The provided language code should follow the ISO 639-1 "
                    "format for languages."
                )
        return value

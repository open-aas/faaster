"""Primitive Data Types Used in Metamodel."""

from pydantic_core import core_schema
from faaster.aas_metamodel.exceptions import InvalidFieldException

import re


FILE_URI_REGEX = re.compile(
    r"^(?:"
    r"/.*|"  # POSIX absolute
    r"\.{1,2}/.*|"  # ./ ou ../
    r"[^/:]+|"  # simple name (without / :)
    r"[A-Za-z]:/.*|"  # Windows absolute
    r"file:(?:[A-Za-z]:/.*|//[^/]+/.*|/.*)|"  # file: URIs
    r"(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)"  # Base64, não-vazio
    r")\Z"
)


class PathType(str):
    """Primitive Data Types Used in Metamodel.

    Valid path according to RFC8089, for relative and absolute file paths.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, _source, _handler):
        """Define a custom Pydantic schema that validates file paths against RFC8089.

        :param cls: The model class applying the custom schema.
        :param _source: The original source schema (unused).
        :param _handler: The handler for schema modification (unused).
        :return: A core schema with validation for file URI paths.
        """

        def validate_path(value: str) -> str:
            if not FILE_URI_REGEX.match(value):
                raise InvalidFieldException(
                    detail=f"'{value}' is not a valid path according to RFC8089."
                )
            return value

        return core_schema.no_info_after_validator_function(
            validate_path,
            core_schema.str_schema(),
        )

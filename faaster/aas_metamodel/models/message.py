"""Data model for Message, representing a message structure."""

from pydantic import Field, field_validator
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.models.message_type import MessageType
from faaster.aas_metamodel.exceptions import InvalidIdException

import re


class Message(DTO):
    """Data model for Message, representing a message structure."""

    code: ConstrainedString = Field(..., min_length=1, max_length=32)
    correlation_id: ConstrainedString = Field(..., min_length=1, max_length=182)
    message_type: MessageType = Field(...)
    text: ConstrainedString = Field(...)
    timestamp: ConstrainedString = Field(...)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value):
        """Validates that the timestamp follows the ISO 8601 format."""
        if value is None:
            return value
        iso8601_regex = re.compile(
            r"^-?(([1-9][0-9]{3})|(0[0-9]{3}))-((0[1-9])|(1[0-2]))-((0[1-9])|([12][0-9])|"
            r"(3[01]))T((([01][0-9])|(2[0-3])):[0-5][0-9]:([0-5][0-9])(\.[0-9]+)?|24:00:00(\.0+)?)"
            r"(Z|\+00:00|-00:00)$"
        )
        if not iso8601_regex.match(value):
            raise InvalidIdException(detail="Invalid timestamp format. Must be in ISO 8601 format.")
        return value

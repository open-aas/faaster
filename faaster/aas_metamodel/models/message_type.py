"""Enumeration for the types of messages."""

from enum import Enum


class MessageType(str, Enum):
    """Enumeration for the types of messages."""

    UNDEFINED = "Undefined"
    INFO = "Info"
    WARNING = "Warning"
    ERROR = "Error"
    EXCEPTION = "Exception"

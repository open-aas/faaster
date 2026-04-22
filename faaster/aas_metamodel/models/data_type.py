"""Data type, can be Blob or Identifier."""

from enum import Enum


class DataType(str, Enum):
    """Data type, can be Blob or Identifier."""

    BLOB = "Blob"
    IDENTIFIER = "Identifier"

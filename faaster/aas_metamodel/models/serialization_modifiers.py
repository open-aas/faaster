"""Enumerations for controlling serialization level and extent of Submodel Elements."""

from enum import Enum


class SerializationModifierLevel(str, Enum):
    """Defines the level of serialization for Submodel Elements."""

    DEEP = "deep"
    CORE = "core"


class SerializationModifierExtent(str, Enum):
    """Defines whether serialization includes or excludes blob values."""

    WITHOUT_BLOB_VALUE = "WithoutBlobValue"
    WITH_BLOB_VALUE = "WithBlobValue"

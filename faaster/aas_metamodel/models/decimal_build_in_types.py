"""Enumeration listing all xsd build in decimal types."""

from enum import Enum


class DecimalBuildInTypes(str, Enum):
    """Enumeration listing all xsd build in decimal types."""

    INTEGER = "xs:integer"
    LONG = "xs:long"
    INT = "xs:int"
    SHORT = "xs:short"
    BYTE = "xs:byte"
    NON_NEGATIVE_INTEGER = "xs:nonNegativeInteger"
    POSITIVE_INTEGER = "xs:positiveInteger"
    UNSIGNED_LONG = "xs:unsignedLong"
    UNSIGNED_INT = "xs:unsignedInt"
    UNSIGNED_SHORT = "xs:unsignedShort"
    UNSIGNED_BYTE = "xs:unsignedByte"
    NON_POSITIVE_LONG = "xs:nonPositiveLong"
    NEGATIVE_INTEGER = "xs:negativeInteger"

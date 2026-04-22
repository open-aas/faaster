"""Enumeration of supported security attribute types."""

from enum import Enum


class SecurityAttributesTypes(str, Enum):
    """Types of security attributes that can be applied to endpoints or data."""

    NONE = "NONE"
    RFC_TLSA = "RFC_TLSA"
    W3C_DID = "V3C_DID"

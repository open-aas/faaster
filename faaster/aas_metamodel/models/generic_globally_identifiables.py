"""Enumeration of different key value types within a key."""

from enum import Enum


class GenericGloballyIdentifiables(str, Enum):
    """Enumeration of different key value types within a key.

    :param GLOBAL_REFERENCE: Global reference.
    """

    GLOBAL_REFERENCE = "GlobalReference"

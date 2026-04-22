"""Enumeration of denoting whether an asset is a type asset or an instance asset."""

from enum import Enum


class AssetKind(str, Enum):
    """Enumeration of denoting whether an asset is a type asset or an instance asset.
    \f
    :param TYPE: Hardware or software element which specifies the common attributes shared by all
    instances of the type.
    :param INSTANCE: Concrete, clearly identifiable component of a certain type
    :param NOT_APPLICABLE: Not applicable.
    """

    TYPE = "Type"
    INSTANCE = "Instance"
    NOT_APPLICABLE = "NotApplicable"

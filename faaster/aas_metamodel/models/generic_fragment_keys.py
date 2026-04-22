"""Enumeration of different fragment key value types within a key."""

from enum import Enum


class GenericFragmentKeys(str, Enum):
    """Enumeration of different fragment key value types within a key.
    \f
    :param FRAGMENT_REFERENCE: Bookmark or a similar local identifier of a subordinate part
    of a primary resource.
    """

    FRAGMENT_REFERENCE = "FragmentReference"

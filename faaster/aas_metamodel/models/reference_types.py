"""Reference types."""

from enum import Enum


class ReferenceTypes(str, Enum):
    """Reference types.

    :param GLOBAL_REFERENCE: Global reference.
    :param MODEL_REFERENCE: Model reference.
    """

    GLOBAL_REFERENCE = "ExternalReference"
    MODEL_REFERENCE = "ModelReference"

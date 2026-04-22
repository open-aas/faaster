"""A set of value reference pairs."""

from typing import List
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.value_reference_pair import ValueReferencePair


class ValueList(DTO):
    """A set of value reference pairs.

    :param value_reference_pairs: A pair of a value together with its global unique ID.
    """

    value_reference_pairs: List[ValueReferencePair]

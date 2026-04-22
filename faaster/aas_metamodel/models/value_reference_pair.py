"""A value reference pair within a value list."""

from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.models.reference import Reference


class ValueReferencePair(DTO):
    """A value reference pair within a value list.

    Each value has a global unique ID defining its semantic.

    :param value: The value of the referenced definition of the value in valueId.
    :param value_id: Global unique ID of the value.
    """

    value: ConstrainedString
    value_id: Reference

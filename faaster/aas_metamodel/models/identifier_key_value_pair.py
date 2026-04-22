"""The key value pair of an Identifier element."""

from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.models.has_semantics import HasSemantics
from faaster.aas_metamodel.models.reference import Reference


class IdentifierKeyValuePair(HasSemantics):
    """The key value pair of an Identifier element."""

    key: ConstrainedString
    value: ConstrainedString
    external_subject_id: Reference

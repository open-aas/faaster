"""A submodel element is an element suitable for the description and differentiation of assets."""

from faaster.aas_metamodel.models.has_data_specification import HasDataSpecification
from faaster.aas_metamodel.models.has_kind import HasKind
from faaster.aas_metamodel.models.has_semantics import HasSemantics
from faaster.aas_metamodel.models.qualifiable import Qualifiable
from faaster.aas_metamodel.models.referable import Referable


class SubmodelElement(
    Referable,
    HasKind,
    HasSemantics,
    Qualifiable,
    HasDataSpecification,
):
    """A submodel element is an element suitable for the description and differentiation of assets.

    It is recommended to add a semanticId to a SubmodelElement.

    idShort is inherited as optional from Referable: direct children of a
    SubmodelElementList have none, and every other container enforces it on
    its children (Constraint AASd-117).
    """


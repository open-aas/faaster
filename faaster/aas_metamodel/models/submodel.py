"""A submodel defines a specific aspect of the asset represented by the AAS."""

from typing import List, Optional
from faaster.aas_metamodel.models.has_data_specification import HasDataSpecification
from faaster.aas_metamodel.models.has_kind import HasKind
from faaster.aas_metamodel.models.has_semantics import HasSemantics
from faaster.aas_metamodel.models.identifiable import Identifiable
from faaster.aas_metamodel.models.qualifiable import Qualifiable
from faaster.aas_metamodel.models.submodel_element_union import SubmodelElementUnion


class Submodel(Identifiable, HasKind, HasSemantics, Qualifiable, HasDataSpecification):
    """A submodel defines a specific aspect of the asset represented by the AAS.

    A submodel is used to structure the digital representation and technical
    functionality of an Administration Shell into distinguishable parts. Each submodel
    refers to a well-defined domain or subject. Submodels can become
    standardized and, thus, become submodels templates.
    """

    submodel_elements: Optional[List[SubmodelElementUnion]] = []

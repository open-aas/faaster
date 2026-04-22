"""The semantics of a property or other elements that may have a semantic description."""

from typing import List, Optional
from faaster.aas_metamodel.models.has_data_specification import HasDataSpecification
from faaster.aas_metamodel.models.identifiable import Identifiable
from faaster.aas_metamodel.models.reference import Reference


class ConceptDescription(Identifiable, HasDataSpecification):
    """The semantics of a property or other elements that may have a semantic description.

    The description of the concept should follow a standardized schema (realized as data
    specification template).

    :param is_case_of: Reference to an external definition the concept is compatible to or was
    derived from.
    """

    is_case_of: Optional[List[Reference]] = []

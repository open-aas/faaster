"""DTO for Submodel descriptors including metadata and communication endpoints."""

from typing import List, Optional
from faaster.aas_metamodel.models.endpoint import Endpoint
from faaster.aas_metamodel.models.has_kind import HasKind
from faaster.aas_metamodel.models.has_semantics import HasSemantics
from faaster.aas_metamodel.models.identifiable_descriptor import IdentifiableDescriptor
from faaster.aas_metamodel.models.qualifiable import Qualifiable


class SubmodelDescriptor(
    IdentifiableDescriptor,
    HasKind,
    HasSemantics,
    Qualifiable,
):
    """DTO representing a Submodel descriptor with metadata and optional endpoints."""

    endpoints: Optional[List[Endpoint]] = []

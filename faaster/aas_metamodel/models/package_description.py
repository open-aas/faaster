"""Response model for list of available AASX packages at the server."""

from typing import List, Optional
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.constrained_string import ConstrainedString


class PackageDescription(DTO):
    """Response model for list of available AASX packages at the server.

    :param aas_ids: Asset Administration Shells Identifiers.
    :param package_id: Package Identifier.
    """

    aas_ids: Optional[List[ConstrainedString]] = []
    package_id: Optional[ConstrainedString] = None

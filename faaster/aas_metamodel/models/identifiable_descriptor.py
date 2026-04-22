"""The identifiable parameter of an element descriptor."""

from typing import Optional
from faaster.aas_metamodel.models.administrative_information import AdministrativeInformation
from faaster.aas_metamodel.models.identifier import Identifier
from faaster.aas_metamodel.models.referable_descriptor import ReferableDescriptor


class IdentifiableDescriptor(ReferableDescriptor):
    """The identifiable parameter of an element descriptor."""

    administration: Optional[AdministrativeInformation] = None
    id: Identifier

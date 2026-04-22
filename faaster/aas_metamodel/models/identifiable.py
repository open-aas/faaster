"""An element that has a globally unique identifier."""

from typing import Optional
from faaster.aas_metamodel.models.administrative_information import AdministrativeInformation
from faaster.aas_metamodel.models.identifier import Identifier
from faaster.aas_metamodel.models.referable import Referable


class Identifiable(Referable):
    """An element that has a globally unique identifier.
    \f
    :param administration: Administrative information of an identifiable element.
    :param id: The globally unique identification of the element.
    """

    administration: Optional[AdministrativeInformation] = None
    id: Identifier

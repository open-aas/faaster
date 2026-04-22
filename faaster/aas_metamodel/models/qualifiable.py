"""The value of a Qualifiable element may be further qualified by one or more qualifiers."""

from typing import List, Optional
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.qualifier import Qualifier


class Qualifiable(DTO):
    """The value of a Qualifiable element may be further qualified by one or more qualifiers.

    :param qualifiers: Additional qualification of a qualifiable element.
    """

    qualifiers: Optional[List[Qualifier]] = []

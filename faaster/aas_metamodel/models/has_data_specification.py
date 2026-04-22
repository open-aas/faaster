"""Element that can be extended by using data specification templates."""

from typing import List, Optional
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.embedded_data_specification import EmbeddedDataSpecification


class HasDataSpecification(DTO):
    """Element that can be extended by using data specification templates.

    A data specification template defines a named set of additional attributes an element
    may or shall have. The data specifications used are explicitly specified with their global ID.

    :param embedded_data_specifications: Global reference to the data specification template used
    by the element.
    """

    embedded_data_specifications: Optional[List[EmbeddedDataSpecification]] = []

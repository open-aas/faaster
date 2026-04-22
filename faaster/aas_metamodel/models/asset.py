"""DTO representing an Asset with identification and data specifications."""

from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.has_data_specification import HasDataSpecification
from faaster.aas_metamodel.models.identifiable import Identifiable


class Asset(DTO):
    """DTO representing an Asset with identification and data specifications."""

    identifiable: Identifiable
    has_data_specification: HasDataSpecification

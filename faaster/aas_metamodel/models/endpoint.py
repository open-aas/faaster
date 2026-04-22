"""DTO for endpoints, including OPC UA and other protocol information."""

from pydantic import Field
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.models.protocol_information import ProtocolInformation


class Endpoint(DTO):
    """DTO representing a communication endpoint with interface and protocol details."""

    interface: ConstrainedString = Field(max_length=128)
    protocol_information: ProtocolInformation

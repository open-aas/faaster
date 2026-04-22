"""DTO for protocol information, including endpoint and security attributes."""

from typing import List, Optional
from pydantic import Field
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.models.security_attributes import SecurityAttributes


class ProtocolInformation(DTO):
    """DTO representing protocol details for an endpoint.

    Including protocol type, version, subprotocol, and security attributes.
    """

    href: ConstrainedString = Field(max_length=2048)
    endpoint_protocol: Optional[ConstrainedString] = Field(None, max_length=128)
    endpoint_protocol_version: List[Optional[ConstrainedString]] = []
    subprotocol: Optional[ConstrainedString] = Field(None, max_length=128)
    subprotocol_body: Optional[ConstrainedString] = Field(None, max_length=128)
    subprotocol_body_encoding: Optional[ConstrainedString] = Field(None, max_length=128)
    security_attributes: Optional[List[SecurityAttributes]] = []

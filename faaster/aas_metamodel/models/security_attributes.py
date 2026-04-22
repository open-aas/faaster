"""DTO representing security attributes with type, key, and value."""

from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.security_attribute_types import SecurityAttributesTypes


class SecurityAttributes(DTO):
    """DTO for a security attribute including its type, key, and value."""

    type: SecurityAttributesTypes
    key: str
    value: str

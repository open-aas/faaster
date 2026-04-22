"""A specific asset ID describes a generic supplementary identifying attribute of the asset."""

from typing import Optional
from pydantic import field_validator
from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.models.has_semantics import HasSemantics
from faaster.aas_metamodel.models.identifier import Identifier
from faaster.aas_metamodel.models.reference import Reference
from faaster.aas_metamodel.exceptions import InvalidFieldException


class SpecificAssetId(HasSemantics):
    """A specific asset ID describes a generic supplementary identifying attribute of the asset.

    The specific asset ID is not necessarily globally unique.

    :param name: Name of the identifier
    :param value: The value of the specific asset identifier with the corresponding name.
    :param external_subject_id: The (external) subject the specific asset ID belongs to
    or has meaning to.
    """

    name: ConstrainedString
    value: Identifier
    external_subject_id: Optional[Reference] = None

    @field_validator("external_subject_id")
    @classmethod
    def validate_external_subject_id(cls, value):
        """Constraint AASd-133.

        SpecificAssetId/externalSubjectId shall be a global reference, i.e.
        Reference/type = ExternalReference.
        """
        if value is None:
            return value

        if value.type != "ExternalReference":
            raise InvalidFieldException(
                detail=(
                    f"Invalid externalSubjectId type: '{value.type}'. "
                    "SpecificAssetId/externalSubjectId shall be a global reference, i.e. "
                    "Reference/type = ExternalReference (Constraint AASd-133)."
                )
            )
        return value

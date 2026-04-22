"""Administrative meta information for an element like version information."""


from typing import Optional
from pydantic import field_validator, model_validator
from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.models.has_data_specification import HasDataSpecification
from faaster.aas_metamodel.models.identifier import Identifier
from faaster.aas_metamodel.models.reference import Reference
from faaster.aas_metamodel.exceptions import InvalidFieldException

import re
import structlog


logger = structlog.get_logger(__name__)


class AdministrativeInformation(HasDataSpecification):
    """Administrative meta information for an element like version information.

    :param revision: revision of the element
    :param version: version of the element
    :param creator: the subject ID of the subject responsible for making the element
    :param template_id: identifier of the template that guided the creation of the element.
    """

    revision: Optional[ConstrainedString] = None
    version: Optional[ConstrainedString] = None
    creator: Optional[Reference] = None
    template_id: Optional[Identifier] = None

    @field_validator("version", mode="before")
    @classmethod
    def validate_version(cls, value: Optional[str]) -> Optional[str]:
        """Constraint AASd-135.

        AdministrativeInformation/version shall have a length of maximum 4 characters.
        """
        if value is None:
            return value
        if not 1 <= len(value) <= 4:
            logger.error(f"Invalid version length: {value}")
            raise InvalidFieldException(
                detail="Version must be a string between 1 and 4 characters "
                "(Constraint AASd-135)."
            )
        if not re.match(r"^([0-9]|[1-9][0-9]*)$", value):
            logger.error(f"Invalid version format: {value}")
            raise InvalidFieldException(
                detail="Version must match the pattern: ^([0-9]|[1-9][0-9]*)$"
            )
        return value

    @field_validator("revision", mode="before")
    @classmethod
    def validate_revision(cls, value: Optional[str]) -> Optional[str]:
        """Constraint AASd-136.

        AdministrativeInformation/version shall have a length of maximum 4 characters.
        """
        if value is None:
            return value
        if not 1 <= len(value) <= 4:
            logger.error(f"Invalid revision length: {len(value)}")
            raise InvalidFieldException(
                detail="Revision must be a string between 1 and 4 characters "
                "(Constraint AASd-136)."
            )
        if not re.match(r"^([0-9]|[1-9][0-9]*)$", value):
            logger.error(f"Invalid revision format: {value}")
            raise InvalidFieldException(
                detail="Revision must match the pattern: ^([0-9]|[1-9][0-9]*)$"
            )
        return value

    @model_validator(mode="after")
    def validate_consistency(self) -> "AdministrativeInformation":
        """Constraint AASd-005.

        If AdministrativeInformation/version is not specified,
        AdministrativeInformation/revision shall also be unspecified. This means that a revision
        requires a version. If there is no version, there is no revision either. Revision is
        optional.
        """
        if self.revision is not None and self.version is None:
            logger.error(f"Revision specified without version: revision={self.revision}, version={self.version}")
            raise InvalidFieldException(
                detail="If 'revision' is specified, 'version' must also be specified. "
                "A revision requires a version (Constraint AASd-005)."
            )
        return self

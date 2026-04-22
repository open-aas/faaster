"""Element that can have a semantic definition plus some supplemental semantic definitions."""

from typing import List, Optional
from pydantic import model_validator
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.reference import Reference
from faaster.aas_metamodel.exceptions import InvalidFieldException


class HasSemantics(DTO):
    """Element that can have a semantic definition plus some supplemental semantic definitions.

    :param semantic_id: Identifier of the semantic definition of the element.
    It is called semantic ID or also main semantic ID of the element.
    :param supplemental_semantic_ids: Identifier of a supplemental semantic definition
    of the element. It is called supplemental semantic ID of the element.
    """

    semantic_id: Optional[Reference] = None
    supplemental_semantic_ids: Optional[List[Reference]] = []

    @model_validator(mode="after")
    def validate_semantic_constraints(self) -> "HasSemantics":
        """Constraint AASd-118.

        A semantic_id must be defined before adding a supplemental_semantic_id.
        """
        if self.supplemental_semantic_ids and not self.semantic_id:
            raise InvalidFieldException(
                detail="A semanticId must be defined before adding a supplementalSemanticId "
                "(Constraint AASd-118)."
            )
        return self

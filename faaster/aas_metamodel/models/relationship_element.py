"""Relationship element that can be annotated with additional data elements."""

from typing import Literal
from pydantic import Field
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.reference import Reference
from faaster.aas_metamodel.models.submodel_element import SubmodelElement


class RelationshipElement(SubmodelElement):
    """Relationship element that can be annotated with additional data elements.

    :param first: Reference to the first element in the relationship taking the role
    of the subject.
    :param second: Reference to the second element in the relationship taking the role
     of the object.
    """

    type_model: Literal[ModelType.RELATIONSHIP_ELEMENT] = Field(
        alias="modelType", default=ModelType.RELATIONSHIP_ELEMENT
    )
    first: Reference
    second: Reference

"""Relationship element that can be annotated with additional data elements."""

from typing import List, Literal, Optional
from pydantic import Field, field_validator
from faaster.aas_metamodel.submodel_element_processor import SubmodelElementProcessor
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.reference import Reference
from faaster.aas_metamodel.models.submodel_element import SubmodelElement
from faaster.aas_metamodel.validators import require_id_shorts


class AnnotatedRelationshipElement(SubmodelElement):
    """Relationship element that can be annotated with additional data elements.

    :param annotations: Data elements that represent annotations that hold for
    the relationship between the two elements. The singular "annotation" of
    older serializations is also accepted.
    """

    type_model: Literal[ModelType.ANNOTATED_RELATIONSHIP_ELEMENT] = Field(
        alias="modelType", default=ModelType.ANNOTATED_RELATIONSHIP_ELEMENT
    )
    annotations: Optional[List[dict]] = []
    first: Reference
    second: Reference

    def __init__(self, **attrs):
        """Initialize an AnnotatedRelationshipElement by processing its annotations.

        :param self: Instance of AnnotatedRelationshipElement.
        :param attrs: Attributes including an optional 'annotations' list.
        :return: None
        """
        if "annotations" not in attrs and "annotation" in attrs:
            attrs["annotations"] = attrs.pop("annotation")

        submodel_element_union, type_model = SubmodelElementProcessor.process_elements(attrs)
        if type_model == "AnnotatedRelationshipElement":
            processed_annotations = []
            for elem in attrs.get("annotations") or []:
                model_type = elem.get("modelType", None) or elem.get("type_model", None)
                instance = getattr(submodel_element_union, model_type)(**elem)
                processed_annotations.append(instance.model_dump(by_alias=True))
            attrs["annotations"] = processed_annotations
        super().__init__(**attrs)

    @field_validator("annotations")
    @classmethod
    def validate_id_shorts(cls, value):
        """Constraint AASd-117 for the annotations of the relationship."""
        require_id_shorts(value, "AnnotatedRelationshipElement")
        return value

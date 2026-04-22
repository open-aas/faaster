"""Relationship element that can be annotated with additional data elements."""

from typing import List, Literal, Optional
from pydantic import Field
from faaster.aas_metamodel.submodel_element_processor import SubmodelElementProcessor
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.reference import Reference
from faaster.aas_metamodel.models.submodel_element import SubmodelElement


class AnnotatedRelationshipElement(SubmodelElement):
    """Relationship element that can be annotated with additional data elements.

    :param annotation: A data element that represents an annotation that holds for
    the relationship between the two elements.
    """

    type_model: Literal[ModelType.ANNOTATED_RELATIONSHIP_ELEMENT] = Field(
        alias="modelType", default=ModelType.ANNOTATED_RELATIONSHIP_ELEMENT
    )
    annotation: Optional[List[dict]] = []
    first: Reference
    second: Reference

    def __init__(self, **attrs):
        """Initialize an AnnotatedRelationshipElement by processing its annotations.

        :param self: Instance of AnnotatedRelationshipElement.
        :param attrs: Attributes including an optional 'annotation' list.
        :return: None
        """
        submodel_element_union, type_model = SubmodelElementProcessor.process_elements(attrs)
        if type_model == "AnnotatedRelationshipElement":
            processed_annotation = []
            for elem in attrs.get("annotation", []):
                model_type = elem.get("modelType", None) or elem.get("type_model", None)
                instance = getattr(submodel_element_union, model_type)(**elem)
                processed_annotation.append(instance.model_dump(by_alias=True))
            attrs["annotation"] = processed_annotation
        super().__init__(**attrs)

"""Is a kind of struct, i.e. a logical encapsulation of multiple named values."""

# pylint: disable=duplicate-code

from collections import Counter
from typing import List, Literal, Optional
from pydantic import Field, field_validator
from faaster.aas_metamodel.submodel_element_processor import SubmodelElementProcessor
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.submodel_element import SubmodelElement
from faaster.aas_metamodel.exceptions import InvalidFieldException


class SubmodelElementCollection(SubmodelElement):
    """Is a kind of struct, i.e. a logical encapsulation of multiple named values.

    It has a fixed number of submodel elements.

    :param value: Submodel element contained in the collection.
    """

    type_model: Literal[ModelType.SUBMODEL_ELEMENT_COLLECTION] = Field(
        alias="modelType", default=ModelType.SUBMODEL_ELEMENT_COLLECTION
    )
    value: Optional[List[dict]] = []

    def __init__(self, **attrs):
        """Initialize a SubmodelElementCollection, processing nested values when provided.

        :param self: Instance of SubmodelElementCollection.
        :param attrs: Attributes dictionary, may include 'value' as a list of elements.
        :return: None
        """
        from_v2_response = attrs.pop("from_v2_response", False)

        if not from_v2_response:
            submodel_element_union, type_model = SubmodelElementProcessor.process_elements(attrs)
            if type_model == "SubmodelElementCollection":
                if "value" in attrs and isinstance(attrs["value"], list):
                    processed_values = []
                    for elem in attrs["value"]:
                        type_model = elem.get("modelType", None) or elem.get("type_model", None)
                        instance = getattr(submodel_element_union, type_model)(**elem)
                        processed_values.append(instance.model_dump(by_alias=True))
                    attrs["value"] = processed_values
        super().__init__(**attrs)

    @field_validator("value")
    @classmethod
    def validate_unique_id_short(cls, value):
        """Validate that each element in 'value' has a unique idShort (AASd-022).

        :param cls: The model class where the validator is applied.
        :param value: List of element dictionaries.
        :return: The validated list of elements.
        :raises InvalidFieldException: If duplicate idShort values are found.
        """
        if not value:
            return value

        id_shorts = []
        for elem in value:
            id_short = elem.get("idShort") or elem.get("id_short")
            if id_short:
                id_shorts.append(id_short)

        duplicates = [item for item, count in Counter(id_shorts).items() if count > 1]
        if duplicates:
            raise InvalidFieldException(
                detail=f"Duplicate idShort(s) found in collection: {', '.join(duplicates)}. "
                f"The idShort of non-identifiable referables must be unique (AASd-022)."
            )

        return value

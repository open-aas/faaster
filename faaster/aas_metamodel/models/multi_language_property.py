"""A property is a data element that has a multi-language value."""

from typing import List, Literal, Optional
from pydantic import Field
from faaster.aas_metamodel.models.data_element import DataElement
from faaster.aas_metamodel.models.lang_string_set import LangStringSet
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.reference import Reference


class MultiLanguageProperty(DataElement):
    """A property is a data element that has a multi-language value.

    :param value: The value of the property instance.
    :param value_id: Reference to the global unique ID of a coded value.
    """

    type_model: Literal[ModelType.MULTI_LANGUAGE_PROPERTY] = Field(
        alias="modelType", default=ModelType.MULTI_LANGUAGE_PROPERTY
    )
    value: Optional[List[LangStringSet]] = []
    value_id: Optional[Reference] = None

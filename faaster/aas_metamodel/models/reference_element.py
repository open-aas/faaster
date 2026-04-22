"""A reference element is a data element that defines a logical reference to another element."""

from typing import Literal, Optional
from pydantic import Field
from faaster.aas_metamodel.models.data_element import DataElement
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.reference import Reference


class ReferenceElement(DataElement):
    """A reference element is a data element that defines a logical reference to another element.

    Within the same or another AAS or a reference to an external object or entity.

    :param value: Global reference to an external object or entity or a logical reference to another
    element within the same or another AAS (i.e. a model reference to a Referable).
    """

    type_model: Literal[ModelType.REFERENCE_ELEMENT] = Field(
        alias="modelType", default=ModelType.REFERENCE_ELEMENT
    )
    value: Optional[Reference] = None

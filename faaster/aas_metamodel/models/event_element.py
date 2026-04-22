"""An event element."""

from pydantic import Field
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.submodel_element import SubmodelElement


class EventElement(SubmodelElement):
    """An event element."""

    type_model: ModelType = Field(default=ModelType.EVENT_ELEMENT, alias="modelType")

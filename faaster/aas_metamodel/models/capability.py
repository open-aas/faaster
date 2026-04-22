"""Implementation-independent description of the potential of an asset."""

from typing import Literal
from pydantic import Field
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.submodel_element import SubmodelElement


class Capability(SubmodelElement):
    """Implementation-independent description of the potential of an asset.

    To achieve a certain effect in the physical or virtual world.
    """

    type_model: Literal[ModelType.CAPABILITY] = Field(
        alias="modelType", default=ModelType.CAPABILITY
    )

"""An element with a kind is an element that can either represent a template or an instance."""

from typing import Optional
from pydantic import Field
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.modeling_kind import ModelingKind


class HasKind(DTO):
    """An element with a kind is an element that can either represent a template or an instance.

    Default for an element is that it is representing an instance.

    :param kind: The kind of the element. Either type or instance.
    Default Value = Instance.
    """

    kind: Optional[ModelingKind] = Field(ModelingKind.INSTANCE)

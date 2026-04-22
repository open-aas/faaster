"""An entity is a submodel element that is used to model entities."""

from typing import List, Literal, Optional
from pydantic import Field, model_validator
from faaster.aas_metamodel.submodel_element_processor import SubmodelElementProcessor
from faaster.aas_metamodel.models.entity_type import EntityType
from faaster.aas_metamodel.models.specific_asset_id import SpecificAssetId
from faaster.aas_metamodel.exceptions import InvalidFieldException
from faaster.aas_metamodel.models.identifier import Identifier
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.submodel_element import SubmodelElement


class Entity(SubmodelElement):
    """An entity is a submodel element that is used to model entities.

    :param statements: Describes statements applicable to the entity by a set of submodel elements,
    typically with a qualified value.
    :param entity_type: Describes whether the entity is a co-managed entity or a
    self-managed entity.
    :param global_asset_id: Global identifier of the asset the entity is representing.
    :param specific_asset_id: Reference to a specific asset ID representing a
    supplementary identifier
    of the asset represented by the Asset Administration Shell.
    """

    type_model: Literal[ModelType.ENTITY] = Field(alias="modelType", default=ModelType.ENTITY)
    statements: Optional[List[dict]] = []
    entity_type: EntityType
    global_asset_id: Optional[Identifier] = None
    specific_asset_id: Optional[SpecificAssetId] = None

    def __init__(self, **attrs):
        """Initialize an Entity, processing nested statements into proper submodel element DTOs.

        :param self: Instance of Entity.
        :param attrs: Attributes dictionary including optional 'statements'.
        :return: None
        """
        submodel_element_union, type_model = SubmodelElementProcessor.process_elements(attrs)
        if type_model == "Entity":
            processed_statements = []
            for elem in attrs.get("statements", []):
                model_type = elem.get("modelType", None) or elem.get("type_model", None)
                instance = getattr(submodel_element_union, model_type)(**elem)
                processed_statements.append(instance.model_dump(by_alias=True))
            attrs["statements"] = processed_statements
        super().__init__(**attrs)

    @model_validator(mode="after")
    def validate_entity_type_restriction(self) -> "Entity":
        """Validate AASd-014 constraint for entity type restrictions.

        :param self: Instance of Entity.
        :return: The validated Entity instance.
        :raises InvalidFieldException: If the constraint AASd-014 is violated.
        """
        if self.entity_type == "CoManagedEntity":
            if self.global_asset_id or self.specific_asset_id:
                raise InvalidFieldException(
                    detail="A co-managed entity has to have neither a globalAssetId nor a "
                    "specificAssetId (Constraint AASd-014)"
                )

        if self.entity_type == "SelfManagedEntity":
            if not self.global_asset_id and not self.specific_asset_id:
                raise InvalidFieldException(
                    detail="A self-managed entity has to have a globalAssetId or a "
                    "specificAssetId (Constraint AASd-014)"
                )

        return self

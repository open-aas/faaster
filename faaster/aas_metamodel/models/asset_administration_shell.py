"""An asset administration shell."""

from typing import List, Optional
from pydantic import field_validator
from faaster.aas_metamodel.models.asset_information import AssetInformation
from faaster.aas_metamodel.models.has_data_specification import HasDataSpecification
from faaster.aas_metamodel.models.identifiable import Identifiable
from faaster.aas_metamodel.models.reference import Reference
from faaster.aas_metamodel.models.reference_types import ReferenceTypes
from faaster.aas_metamodel.exceptions import InvalidFieldException


class AssetAdministrationShell(Identifiable, HasDataSpecification):
    """An asset administration shell.

    :param derived_from: The reference to the AAS was derived from.
    :param asset_information: Meta information about the asset the AAS is representing.
    :param submodels: A submodel is a description of an aspect of the asset the AAS is representing.
    The asset of an AAS is typically described by one or more submodels.
    Temporarily no submodel might be assigned to the AAS.
    """

    derived_from: Optional[Reference] = None
    asset_information: AssetInformation
    submodels: Optional[List[Reference]] = []

    @field_validator("derived_from", mode="after")
    @classmethod
    def validate_derived_from(cls, value):
        """Ensure that the derivedFrom field is a ModelReference to another AAS.

        :param cls: The model class where the validator is applied.
        :param value: The provided 'derivedFrom' field value.
        :return: The validated 'derivedFrom' value.
        :raises InvalidFieldException: If the value is not a ModelReference to an AAS.
        """
        if value:
            if value.type != ReferenceTypes.MODEL_REFERENCE:
                raise InvalidFieldException(
                    detail="The 'derivedFrom' field must be of type 'ModelReference' and refer to "
                    "another Asset Administration Shell."
                )

        return value

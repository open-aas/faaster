"""AssetInformation identifying metadata of the asset that is represented by an AAS is defined."""

from typing import List, Optional
from pydantic import model_validator
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.asset_kind import AssetKind
from faaster.aas_metamodel.models.identifier import Identifier
from faaster.aas_metamodel.models.resource import Resource
from faaster.aas_metamodel.models.specific_asset_id import SpecificAssetId
from faaster.aas_metamodel.exceptions import InvalidFieldException


class AssetInformation(DTO):
    """AssetInformation identifying metadata of the asset that is represented by an AAS is defined.

    The asset may either represent an asset type or an asset instance.

    :param asset_kind: Denotes whether the Asset is of kind “Type” or “Instance”.
    :param specific_asset_ids: Additional domain specific, typically proprietary identifier
    for the asset like e.g. serial number etc.
    :param global_asset_id: Global identifier of the asset the AAS is representing.
    :param default_thumbnail: Thumbnail of the asset represented by the Asset Administration Shell.
    Used as default.
    """

    asset_kind: AssetKind
    asset_type: Optional[Identifier] = None
    specific_asset_ids: Optional[List[SpecificAssetId]] = []
    global_asset_id: Optional[Identifier] = None
    default_thumbnail: Optional[Resource] = None

    @model_validator(mode="after")
    def validate_global_or_specific(self) -> "AssetInformation":
        """Constraint AASd-131.

        The globalAssetId or at least one specificAssetId shall be defined for AssetInformation.
        """
        if not self.global_asset_id and not (
            self.specific_asset_ids and len(self.specific_asset_ids) > 0
        ):
            raise InvalidFieldException(
                detail="The globalAssetId or at least one specificAssetId must be defined "
                "(Constraint AASd-131)."
            )
        return self

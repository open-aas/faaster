"""An Asset Administration Shell descriptor."""

from typing import List, Optional
from pydantic import Field
from faaster.aas_metamodel.models.asset_kind import AssetKind
from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.models.endpoint import Endpoint
from faaster.aas_metamodel.models.identifiable_descriptor import IdentifiableDescriptor
from faaster.aas_metamodel.models.specific_asset_id import SpecificAssetId
from faaster.aas_metamodel.models.submodel_descriptor import SubmodelDescriptor

class AssetAdministrationShellDescriptor(
    IdentifiableDescriptor,
):
    """An Asset Administration Shell descriptor."""

    asset_kind: Optional[AssetKind] = Field(default=AssetKind.NOT_APPLICABLE)
    asset_type: Optional[ConstrainedString] = None
    specific_asset_ids: Optional[List[SpecificAssetId]] = []
    global_asset_id: Optional[ConstrainedString] = None
    endpoints: Optional[List[Endpoint]] = []
    # connection_status: Optional[ConnectionStatus] = ConnectionStatus.OFFLINE
    submodel_descriptors: Optional[List[SubmodelDescriptor]] = []

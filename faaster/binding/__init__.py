"""
Vínculo declarativo AAS ↔ ativo pelos submodelos AID (IDTA 02017) e
AIMC (IDTA 02027). Ver binder.AssetBinder.
"""

from faaster.binding.binder import AssetBinder
from faaster.binding.drivers.base import IAssetDriver

__all__ = ["AssetBinder", "IAssetDriver"]

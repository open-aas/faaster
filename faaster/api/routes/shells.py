"""
Asset Administration Shell Repository Service Specification — leitura (SSP-002).

Inclui o superpath /shells/{aasIdentifier}/submodels/{submodelIdentifier}/...,
que dá acesso aos submodelos referenciados pela AAS com as mesmas rotas do
Submodel Repository.
"""
from typing import List, Optional

from fastapi import APIRouter, Query, Request

from ..encoding import b64url_decode
from ..pagination import paginate, paged_result
from ..repository import decode_specific_asset_id
from ..serializer import Level
from .submodel_resource import (
    CURSOR,
    LIMIT,
    REFERENCE_LEVEL,
    build_submodel_router,
    check_reference_level,
    repository,
)


_TAGS = ["Asset Administration Shell Repository API"]

router = APIRouter(tags=_TAGS)

_ASSET_IDS = Query(None, alias="assetIds")
_ID_SHORT = Query(None, alias="idShort")


def _shell_reference(aas_id: str) -> dict:
    return {
        "type": "ModelReference",
        "keys": [{"type": "AssetAdministrationShell", "value": aas_id}],
    }


def _list_shells(request: Request, asset_ids: Optional[List[str]], id_short: Optional[str]) -> list:
    return repository(request).list_shells(
        id_short=id_short,
        asset_ids=[decode_specific_asset_id(a) for a in asset_ids] if asset_ids else None,
    )


def _get_shell(request: Request, aas_identifier: str) -> dict:
    aas_id = b64url_decode(aas_identifier, what="aasIdentifier")
    return repository(request).get_shell(aas_id)


# =============================================================================
# /shells
# =============================================================================

@router.get("/shells", operation_id="GetAllAssetAdministrationShells")
async def get_all_shells(
    request: Request,
    asset_ids: Optional[List[str]] = _ASSET_IDS,
    id_short: Optional[str] = _ID_SHORT,
    limit: Optional[int] = LIMIT,
    cursor: Optional[str] = CURSOR,
) -> dict:
    page, next_cursor = paginate(_list_shells(request, asset_ids, id_short), limit, cursor)
    return paged_result(page, next_cursor)


@router.get("/shells/$reference", operation_id="GetAllAssetAdministrationShells-Reference")
async def get_all_shells_reference(
    request: Request,
    asset_ids: Optional[List[str]] = _ASSET_IDS,
    id_short: Optional[str] = _ID_SHORT,
    limit: Optional[int] = LIMIT,
    cursor: Optional[str] = CURSOR,
) -> dict:
    page, next_cursor = paginate(_list_shells(request, asset_ids, id_short), limit, cursor)
    return paged_result([_shell_reference(s["id"]) for s in page], next_cursor)


# =============================================================================
# /shells/{aasIdentifier}
# =============================================================================

@router.get("/shells/{aas_identifier}", operation_id="GetAssetAdministrationShellById")
async def get_shell_by_id(request: Request, aas_identifier: str) -> dict:
    return _get_shell(request, aas_identifier)


@router.get(
    "/shells/{aas_identifier}/$reference",
    operation_id="GetAssetAdministrationShellById-Reference_AasRepository",
)
async def get_shell_by_id_reference(
    request: Request,
    aas_identifier: str,
    level: Optional[Level] = REFERENCE_LEVEL,
) -> dict:
    check_reference_level(level)
    return _shell_reference(_get_shell(request, aas_identifier)["id"])


@router.get(
    "/shells/{aas_identifier}/asset-information",
    operation_id="GetAssetInformation_AasRepository",
)
async def get_asset_information(request: Request, aas_identifier: str) -> dict:
    return _get_shell(request, aas_identifier).get("assetInformation") or {}


@router.get(
    "/shells/{aas_identifier}/submodel-refs",
    operation_id="GetAllSubmodelReferences_AasRepository",
)
async def get_all_submodel_references(
    request: Request,
    aas_identifier: str,
    limit: Optional[int] = LIMIT,
    cursor: Optional[str] = CURSOR,
) -> dict:
    shell = _get_shell(request, aas_identifier)
    page, next_cursor = paginate(shell.get("submodels") or [], limit, cursor)
    return paged_result(page, next_cursor)


# =============================================================================
# /shells/{aasIdentifier}/submodels/{submodelIdentifier}/...
# =============================================================================

def _resolve_shell_submodel(request: Request, aas_identifier: str, submodel_identifier: str) -> dict:
    aas_id = b64url_decode(aas_identifier, what="aasIdentifier")
    submodel_id = b64url_decode(submodel_identifier, what="submodelIdentifier")
    return repository(request).get_shell_submodel(aas_id, submodel_id)


router.include_router(
    build_submodel_router(
        prefix="/shells/{aas_identifier}/submodels/{submodel_identifier}",
        resolve_submodel=_resolve_shell_submodel,
        operation_id=lambda name: f"{name}_AasRepository",
        tags=_TAGS,
    )
)

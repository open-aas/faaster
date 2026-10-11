"""
Submodel Repository Service Specification — leitura (SSP-002) e escrita.

Cada recurso aceita os modificadores de conteúdo como sufixo do path
($metadata, $value, $reference, $path), ver faaster/api/modifiers.py.
As rotas de um submodelo individual vêm de submodel_resource.py.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import JSONResponse

from .. import modifiers
from ..encoding import b64url_decode, b64url_encode
from ..pagination import paginate, paged_result
from ..repository import decode_semantic_id
from ..serializer import Extent, Level
from .submodel_resource import (
    CURSOR as _CURSOR,
    EXTENT as _EXTENT,
    LEVEL as _LEVEL,
    LIMIT as _LIMIT,
    REFERENCE_LEVEL as _REFERENCE_LEVEL,
    build_submodel_router,
    check_metadata_modifiers as _check_metadata_modifiers,
    check_reference_level as _check_reference_level,
    editor as _editor,
    repository as _repository,
    serializer as _serializer,
)


_TAGS = ["Submodel Repository API"]

router = APIRouter(tags=_TAGS)


def _list_submodels(request: Request, semantic_id: Optional[str], id_short: Optional[str]) -> List[Dict[str, Any]]:
    return _repository(request).list_submodels(
        id_short=id_short,
        semantic_id=decode_semantic_id(semantic_id) if semantic_id else None,
    )


_SEMANTIC_ID = Query(None, alias="semanticId", min_length=1)
_ID_SHORT = Query(None, alias="idShort")


# =============================================================================
# /submodels
# =============================================================================

@router.get("/submodels", operation_id="GetAllSubmodels")
async def get_all_submodels(
    request: Request,
    semantic_id: Optional[str] = _SEMANTIC_ID,
    id_short: Optional[str] = _ID_SHORT,
    limit: Optional[int] = _LIMIT,
    cursor: Optional[str] = _CURSOR,
    level: Level = _LEVEL,
    extent: Extent = _EXTENT,
) -> dict:
    page, next_cursor = paginate(_list_submodels(request, semantic_id, id_short), limit, cursor)

    serializer = _serializer(request)
    result = [await serializer.submodel(s, level, extent) for s in page]
    return paged_result(result, next_cursor)


@router.get("/submodels/$metadata", operation_id="GetAllSubmodels-Metadata")
async def get_all_submodels_metadata(
    request: Request,
    semantic_id: Optional[str] = _SEMANTIC_ID,
    id_short: Optional[str] = _ID_SHORT,
    limit: Optional[int] = _LIMIT,
    cursor: Optional[str] = _CURSOR,
) -> dict:
    _check_metadata_modifiers(request)
    page, next_cursor = paginate(_list_submodels(request, semantic_id, id_short), limit, cursor)
    return paged_result([modifiers.metadata(s) for s in page], next_cursor)


@router.get("/submodels/$value", operation_id="GetAllSubmodels-ValueOnly")
async def get_all_submodels_value_only(
    request: Request,
    semantic_id: Optional[str] = _SEMANTIC_ID,
    id_short: Optional[str] = _ID_SHORT,
    limit: Optional[int] = _LIMIT,
    cursor: Optional[str] = _CURSOR,
    level: Level = _LEVEL,
    extent: Extent = _EXTENT,
) -> dict:
    page, next_cursor = paginate(_list_submodels(request, semantic_id, id_short), limit, cursor)

    serializer = _serializer(request)
    result = [
        modifiers.submodel_value_only(await serializer.submodel(s, level, extent))
        for s in page
    ]
    return paged_result(result, next_cursor)


@router.get("/submodels/$reference", operation_id="GetAllSubmodels-Reference")
async def get_all_submodels_reference(
    request: Request,
    semantic_id: Optional[str] = _SEMANTIC_ID,
    id_short: Optional[str] = _ID_SHORT,
    limit: Optional[int] = _LIMIT,
    cursor: Optional[str] = _CURSOR,
    level: Optional[Level] = _REFERENCE_LEVEL,
) -> dict:
    _check_reference_level(level)
    page, next_cursor = paginate(_list_submodels(request, semantic_id, id_short), limit, cursor)
    return paged_result([modifiers.submodel_reference(s["id"]) for s in page], next_cursor)


@router.get("/submodels/$path", operation_id="GetAllSubmodels-Path")
async def get_all_submodels_path(
    request: Request,
    semantic_id: Optional[str] = _SEMANTIC_ID,
    id_short: Optional[str] = _ID_SHORT,
    limit: Optional[int] = _LIMIT,
    cursor: Optional[str] = _CURSOR,
    level: Level = _LEVEL,
) -> dict:
    page, next_cursor = paginate(_list_submodels(request, semantic_id, id_short), limit, cursor)

    result: List[str] = []
    for submodel in page:
        result.extend(
            modifiers.top_level_paths(submodel.get("submodelElements") or [], level == Level.deep)
        )
    return paged_result(result, next_cursor)


@router.post("/submodels", operation_id="PostSubmodel", status_code=201)
async def post_submodel(request: Request, body: Dict[str, Any] = Body(..., description="Submodel")) -> JSONResponse:
    submodel = await _editor(request).create_submodel(body)
    location = f"{str(request.url.replace(query='')).rstrip('/')}/{b64url_encode(submodel['id'])}"
    rendered = await _serializer(request).submodel(submodel)
    return JSONResponse(rendered, status_code=201, headers={"Location": location})


# =============================================================================
# /submodels/{submodelIdentifier}/...
# =============================================================================

def _resolve_submodel(request: Request, submodel_identifier: str) -> dict:
    submodel_id = b64url_decode(submodel_identifier, what="submodelIdentifier")
    return _repository(request).get_submodel(submodel_id)


def _operation_id(name: str) -> str:
    # na spec, só as operações do submodelo em si não levam o sufixo _SubmodelRepo
    if name.startswith(("GetSubmodelById", "PutSubmodelById", "PatchSubmodelById", "DeleteSubmodelById")) \
            or name == "GetAllSubmodelElements":
        return name
    return f"{name}_SubmodelRepo"


router.include_router(
    build_submodel_router(
        prefix="/submodels/{submodel_identifier}",
        resolve_submodel=_resolve_submodel,
        operation_id=_operation_id,
        tags=_TAGS,
        can_create_submodel=True,
    )
)

"""
GenerateSerializationByIds — GET /serialization.

Gera um Environment com as AAS e submodelos pedidos (submodelos com valores
vivos do OPC UA). Por enquanto só em JSON; XML e AASX respondem 501.
"""
from typing import List, Optional

from fastapi import APIRouter, Query, Request

from ..encoding import b64url_decode
from ..errors import NotImplementedApiError
from ..serializer import Extent, Level
from .submodel_resource import repository, serializer


router = APIRouter(tags=["Serialization API"])

_JSON = "application/json"
_UNSUPPORTED = ("application/xml", "application/aas+zip", "application/aasx+xml")


def _check_accept(request: Request) -> None:
    accept = request.headers.get("accept", "")
    if not accept or "*/*" in accept or _JSON in accept or "application/*" in accept:
        return
    if any(media in accept for media in _UNSUPPORTED):
        raise NotImplementedApiError(
            f"Serialization format '{accept}' is not supported yet, use '{_JSON}'"
        )


@router.get("/serialization", operation_id="GenerateSerializationByIds")
async def generate_serialization_by_ids(
    request: Request,
    aas_ids: Optional[List[str]] = Query(None, alias="aasIds"),
    submodel_ids: Optional[List[str]] = Query(None, alias="submodelIds"),
    include_concept_descriptions: bool = Query(True, alias="includeConceptDescriptions"),
) -> dict:
    _check_accept(request)
    repo = repository(request)

    # sem nenhum id, serializa o Environment inteiro deste servidor
    select_all = not aas_ids and not submodel_ids

    if select_all:
        shells = repo.list_shells()
        submodels = repo.list_submodels()
    else:
        shells = [repo.get_shell(b64url_decode(i, what="aasIds")) for i in aas_ids or []]
        submodels = [repo.get_submodel(b64url_decode(i, what="submodelIds")) for i in submodel_ids or []]

    rendered = [
        await serializer(request).submodel(s, Level.deep, Extent.with_blob_value)
        for s in submodels
    ]

    environment: dict = {
        "assetAdministrationShells": shells,
        "submodels": rendered,
    }
    if include_concept_descriptions:
        environment["conceptDescriptions"] = repo.referenced_concept_descriptions(shells + submodels)

    # a Part 1 exige listas não vazias: omite as que ficaram vazias
    return {k: v for k, v in environment.items() if v}

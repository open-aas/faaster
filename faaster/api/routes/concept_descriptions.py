"""
Concept Description Repository Service Specification — operações de leitura.

A spec só define o perfil completo (SSP-001, com escrita); por isso estas rotas
ainda não declaram perfil em /description.
"""
from typing import Optional

from fastapi import APIRouter, Query, Request

from ..encoding import b64url_decode
from ..pagination import paginate, paged_result
from ..repository import decode_semantic_id
from .submodel_resource import CURSOR, LIMIT, repository


router = APIRouter(tags=["Concept Description Repository API"])


@router.get("/concept-descriptions", operation_id="GetAllConceptDescriptions")
async def get_all_concept_descriptions(
    request: Request,
    id_short: Optional[str] = Query(None, alias="idShort"),
    is_case_of: Optional[str] = Query(None, alias="isCaseOf"),
    data_specification_ref: Optional[str] = Query(None, alias="dataSpecificationRef"),
    limit: Optional[int] = LIMIT,
    cursor: Optional[str] = CURSOR,
) -> dict:
    # isCaseOf e dataSpecificationRef: Reference em JSON + base64url, como ?semanticId
    concept_descriptions = repository(request).list_concept_descriptions(
        id_short=id_short,
        is_case_of=decode_semantic_id(is_case_of) if is_case_of else None,
        data_specification_ref=(
            decode_semantic_id(data_specification_ref) if data_specification_ref else None
        ),
    )
    page, next_cursor = paginate(concept_descriptions, limit, cursor)
    return paged_result(page, next_cursor)


@router.get("/concept-descriptions/{cd_identifier}", operation_id="GetConceptDescriptionById")
async def get_concept_description_by_id(request: Request, cd_identifier: str) -> dict:
    cd_id = b64url_decode(cd_identifier, what="cdIdentifier")
    return repository(request).get_concept_description(cd_id)

"""
Rotas de UM submodelo e seus elementos: leitura com os modificadores
$metadata, $value, $reference e $path, escrita de valores (PATCH $value),
escrita estrutural (POST/PUT/PATCH/DELETE) e invocação de Operations
(invoke, invoke-async, operation-status/-results).

O mesmo conjunto é montado em dois lugares, mudando só como o submodelo é
resolvido:
  - Submodel Repository: /submodels/{submodelIdentifier}/...
  - AAS Repository (superpath): /shells/{aasIdentifier}/submodels/{submodelIdentifier}/...
"""
from typing import Any, Callable, Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from .. import modifiers
from ..encoding import b64url_decode, b64url_encode
from ..errors import BadRequestError
from ..pagination import paginate, paged_result
from ..repository import AASRepository
from ..serializer import AASSerializer, Extent, Level
from ..editor import StructureEditor
from ..operations import OperationInvoker
from ..writer import ValueWriter


# Parâmetros de query compartilhados
LIMIT = Query(None, ge=1)
CURSOR = Query(None)
LEVEL = Query(Level.deep)
EXTENT = Query(Extent.without_blob_value)
REFERENCE_LEVEL = Query(None, deprecated=True)
# em PATCH a spec só admite level=core
PATCH_LEVEL = Query(Level.core)
VALUE_ONLY_BODY = Body(..., description="Valor na representação ValueOnly")
OPERATION_REQUEST = Body(..., description="OperationRequest (ou OperationRequestValueOnly em .../$value)")
SUBMODEL_BODY = Body(..., description="Submodel")
ELEMENT_BODY = Body(..., description="SubmodelElement")


def repository(request: Request) -> AASRepository:
    return request.app.state.repository


def serializer(request: Request) -> AASSerializer:
    return request.app.state.serializer


def writer(request: Request) -> ValueWriter:
    return request.app.state.writer


def editor(request: Request) -> StructureEditor:
    return request.app.state.editor


def element_url(request: Request, id_short_path: str) -> str:
    """URL do elemento no mesmo recurso (repositório ou superpath) da requisição."""
    base = str(request.url.replace(query="")).rsplit("/submodel-elements", 1)[0]
    return f"{base}/submodel-elements/{quote(id_short_path, safe='.')}"


def invoker(request: Request) -> OperationInvoker:
    return request.app.state.invoker


def _sibling_url(request: Request, segment: str, replacement: str) -> str:
    """URL da Operation com o último segmento `segment...` trocado por `replacement`."""
    url = str(request.url.replace(query=""))
    return f"{url.rsplit(segment, 1)[0]}{replacement}"


def check_patch_level(level: Level) -> None:
    if level != Level.core:
        raise BadRequestError("Only level=core is allowed for PATCH operations")


def check_metadata_modifiers(request: Request) -> None:
    """Modifier Constraints: Metadata não combina com level nem com withBlobValue."""
    if "level" in request.query_params:
        raise BadRequestError("The level modifier must not be used with Content=Metadata")
    if request.query_params.get("extent") == Extent.with_blob_value.value:
        raise BadRequestError("Content=Metadata cannot be combined with Extent=WithBLOBValue")


def check_reference_level(level: Optional[Level]) -> None:
    """Modifier Constraints: Reference não combina com level=deep."""
    if level == Level.deep:
        raise BadRequestError("Content=Reference cannot be combined with Level=Deep")


def build_submodel_router(
    prefix: str,
    resolve_submodel: Callable[..., Dict[str, Any]],
    operation_id: Callable[[str], str],
    tags: list,
    can_create_submodel: bool = False,
) -> APIRouter:
    """
    resolve_submodel: dependência FastAPI que lê os parâmetros de path do
    prefixo e devolve o submodelo (ou levanta NotFoundError).
    operation_id: nome base da operação → operationId da spec para este serviço.
    can_create_submodel: PUT cria o submodelo quando ele não existe.
    """
    router = APIRouter(tags=tags)
    Submodel = Depends(resolve_submodel)

    # -------------------------------------------------------------------------
    # Submodelo
    # -------------------------------------------------------------------------

    @router.get(prefix, operation_id=operation_id("GetSubmodelById"))
    async def get_submodel(
        request: Request,
        submodel: dict = Submodel,
        level: Level = LEVEL,
        extent: Extent = EXTENT,
    ) -> dict:
        return await serializer(request).submodel(submodel, level, extent)

    @router.get(f"{prefix}/$metadata", operation_id=operation_id("GetSubmodelById-Metadata"))
    async def get_submodel_metadata(request: Request, submodel: dict = Submodel) -> dict:
        check_metadata_modifiers(request)
        return modifiers.metadata(submodel)

    @router.get(f"{prefix}/$value", operation_id=operation_id("GetSubmodelById-ValueOnly"))
    async def get_submodel_value_only(
        request: Request,
        submodel: dict = Submodel,
        level: Level = LEVEL,
        extent: Extent = EXTENT,
    ) -> dict:
        rendered = await serializer(request).submodel(submodel, level, extent)
        return modifiers.submodel_value_only(rendered)

    @router.patch(
        f"{prefix}/$value",
        operation_id=operation_id("PatchSubmodelById-ValueOnly"),
        status_code=204,
        response_class=Response,
    )
    async def patch_submodel_value_only(
        request: Request,
        submodel: dict = Submodel,
        level: Level = PATCH_LEVEL,
        value: Any = VALUE_ONLY_BODY,
    ) -> Response:
        check_patch_level(level)
        writes = writer(request).plan_submodel(submodel, value)
        await writer(request).apply(submodel["id"], writes)
        return Response(status_code=204)

    @router.get(f"{prefix}/$reference", operation_id=operation_id("GetSubmodelById-Reference"))
    async def get_submodel_reference(
        submodel: dict = Submodel,
        level: Optional[Level] = REFERENCE_LEVEL,
    ) -> dict:
        check_reference_level(level)
        return modifiers.submodel_reference(submodel["id"])

    @router.get(f"{prefix}/$path", operation_id=operation_id("GetSubmodelById-Path"))
    async def get_submodel_path(submodel: dict = Submodel, level: Level = LEVEL) -> list:
        return modifiers.top_level_paths(submodel.get("submodelElements") or [], level == Level.deep)

    # -------------------------------------------------------------------------
    # Todos os elementos do submodelo
    # -------------------------------------------------------------------------

    elements = f"{prefix}/submodel-elements"

    @router.get(elements, operation_id=operation_id("GetAllSubmodelElements"))
    async def get_all_elements(
        request: Request,
        submodel: dict = Submodel,
        limit: Optional[int] = LIMIT,
        cursor: Optional[str] = CURSOR,
        level: Level = LEVEL,
        extent: Extent = EXTENT,
    ) -> dict:
        page, next_cursor = paginate(submodel.get("submodelElements") or [], limit, cursor)
        result = await serializer(request).submodel_elements(page, submodel["id"], level, extent)
        return paged_result(result, next_cursor)

    @router.get(f"{elements}/$metadata", operation_id=operation_id("GetAllSubmodelElements-Metadata"))
    async def get_all_elements_metadata(
        request: Request,
        submodel: dict = Submodel,
        limit: Optional[int] = LIMIT,
        cursor: Optional[str] = CURSOR,
    ) -> dict:
        check_metadata_modifiers(request)
        page, next_cursor = paginate(submodel.get("submodelElements") or [], limit, cursor)
        return paged_result([modifiers.metadata(e) for e in page], next_cursor)

    @router.get(f"{elements}/$value", operation_id=operation_id("GetAllSubmodelElements-ValueOnly"))
    async def get_all_elements_value_only(
        request: Request,
        submodel: dict = Submodel,
        limit: Optional[int] = LIMIT,
        cursor: Optional[str] = CURSOR,
        level: Level = LEVEL,
        extent: Extent = EXTENT,
    ) -> dict:
        page, next_cursor = paginate(submodel.get("submodelElements") or [], limit, cursor)
        rendered = await serializer(request).submodel_elements(page, submodel["id"], level, extent)
        return paged_result(modifiers.elements_value_only(rendered), next_cursor)

    @router.get(f"{elements}/$reference", operation_id=operation_id("GetAllSubmodelElements-Reference"))
    async def get_all_elements_reference(
        submodel: dict = Submodel,
        limit: Optional[int] = LIMIT,
        cursor: Optional[str] = CURSOR,
        level: Optional[Level] = REFERENCE_LEVEL,
    ) -> dict:
        check_reference_level(level)
        page, next_cursor = paginate(submodel.get("submodelElements") or [], limit, cursor)
        result = [
            modifiers.element_reference(submodel["id"], [(e, e.get("idShort", ""))])
            for e in page
        ]
        return paged_result(result, next_cursor)

    @router.get(f"{elements}/$path", operation_id=operation_id("GetAllSubmodelElements-Path"))
    async def get_all_elements_path(
        submodel: dict = Submodel,
        limit: Optional[int] = LIMIT,
        cursor: Optional[str] = CURSOR,
        level: Level = LEVEL,
    ) -> dict:
        page, next_cursor = paginate(submodel.get("submodelElements") or [], limit, cursor)
        return paged_result(modifiers.top_level_paths(page, level == Level.deep), next_cursor)

    # -------------------------------------------------------------------------
    # Elemento por idShortPath
    # -------------------------------------------------------------------------

    element = f"{elements}/{{id_short_path}}"

    @router.get(element, operation_id=operation_id("GetSubmodelElementByPath"))
    async def get_element(
        request: Request,
        id_short_path: str,
        submodel: dict = Submodel,
        level: Level = LEVEL,
        extent: Extent = EXTENT,
    ) -> dict:
        found = repository(request).get_submodel_element(submodel["id"], id_short_path)
        return await serializer(request).submodel_element(
            found, submodel["id"], id_short_path, level, extent
        )

    @router.get(f"{element}/$metadata", operation_id=operation_id("GetSubmodelElementByPath-Metadata"))
    async def get_element_metadata(
        request: Request,
        id_short_path: str,
        submodel: dict = Submodel,
    ) -> dict:
        check_metadata_modifiers(request)
        return modifiers.metadata(repository(request).get_submodel_element(submodel["id"], id_short_path))

    @router.get(f"{element}/$value", operation_id=operation_id("GetSubmodelElementByPath-ValueOnly"))
    async def get_element_value_only(
        request: Request,
        id_short_path: str,
        submodel: dict = Submodel,
        level: Level = LEVEL,
        extent: Extent = EXTENT,
    ) -> Any:
        found = repository(request).get_submodel_element(submodel["id"], id_short_path)
        rendered = await serializer(request).submodel_element(
            found, submodel["id"], id_short_path, level, extent
        )
        return modifiers.element_value_only(rendered)

    @router.patch(
        f"{element}/$value",
        operation_id=operation_id("PatchSubmodelElementByPath-ValueOnly"),
        status_code=204,
        response_class=Response,
    )
    async def patch_element_value_only(
        request: Request,
        id_short_path: str,
        submodel: dict = Submodel,
        level: Level = PATCH_LEVEL,
        value: Any = VALUE_ONLY_BODY,
    ) -> Response:
        check_patch_level(level)
        found = repository(request).get_submodel_element(submodel["id"], id_short_path)
        writes = writer(request).plan_element(found, submodel["id"], id_short_path, value)
        await writer(request).apply(submodel["id"], writes)
        return Response(status_code=204)

    @router.get(f"{element}/$reference", operation_id=operation_id("GetSubmodelElementByPath-Reference"))
    async def get_element_reference(
        request: Request,
        id_short_path: str,
        submodel: dict = Submodel,
        level: Optional[Level] = REFERENCE_LEVEL,
    ) -> dict:
        check_reference_level(level)
        chain = repository(request).get_submodel_element_chain(submodel["id"], id_short_path)
        return modifiers.element_reference(submodel["id"], chain)

    @router.get(f"{element}/$path", operation_id=operation_id("GetSubmodelElementByPath-Path"))
    async def get_element_path(
        request: Request,
        id_short_path: str,
        submodel: dict = Submodel,
        level: Level = LEVEL,
    ) -> list:
        found = repository(request).get_submodel_element(submodel["id"], id_short_path)
        return modifiers.element_paths(found, id_short_path, level == Level.deep)

    # -------------------------------------------------------------------------
    # Escrita estrutural — submodelo
    # -------------------------------------------------------------------------

    def aas_id(request: Request) -> Optional[str]:
        encoded = request.path_params.get("aas_identifier")
        return b64url_decode(encoded, what="aasIdentifier") if encoded else None

    @router.put(prefix, operation_id=operation_id("PutSubmodelById"), status_code=204, response_class=Response)
    async def put_submodel(
        request: Request,
        submodel_identifier: str,
        body: Dict[str, Any] = SUBMODEL_BODY,
    ) -> Response:
        submodel_id = b64url_decode(submodel_identifier, what="submodelIdentifier")
        if not (can_create_submodel and not repository(request).has_submodel(submodel_id)):
            # no superpath o submodelo precisa existir e ser referenciado pela AAS
            resolve_submodel(request, **request.path_params)

        created = await editor(request).put_submodel(submodel_id, body)
        if not created:
            return Response(status_code=204)
        rendered = await serializer(request).submodel(repository(request).get_submodel(submodel_id))
        return JSONResponse(rendered, status_code=201, headers={"Location": str(request.url.replace(query=""))})

    @router.patch(prefix, operation_id=operation_id("PatchSubmodelById"), status_code=204, response_class=Response)
    async def patch_submodel(
        request: Request,
        submodel: dict = Submodel,
        level: Level = PATCH_LEVEL,
        body: Dict[str, Any] = SUBMODEL_BODY,
    ) -> Response:
        check_patch_level(level)
        await editor(request).patch_submodel(submodel["id"], body)
        return Response(status_code=204)

    @router.patch(
        f"{prefix}/$metadata",
        operation_id=operation_id("PatchSubmodelById-Metadata"),
        status_code=204,
        response_class=Response,
    )
    async def patch_submodel_metadata(
        request: Request,
        submodel: dict = Submodel,
        body: Dict[str, Any] = SUBMODEL_BODY,
    ) -> Response:
        await editor(request).patch_submodel(submodel["id"], body)
        return Response(status_code=204)

    @router.delete(prefix, operation_id=operation_id("DeleteSubmodelById"), status_code=204, response_class=Response)
    async def delete_submodel(request: Request, submodel: dict = Submodel) -> Response:
        # pelo superpath, a referência na AAS também é removida
        await editor(request).delete_submodel(submodel["id"], aas_id=aas_id(request))
        return Response(status_code=204)

    # -------------------------------------------------------------------------
    # Escrita estrutural — elementos
    # -------------------------------------------------------------------------

    async def created_element(request: Request, submodel_id: str, path: str, element: dict) -> JSONResponse:
        rendered = await serializer(request).submodel_element(element, submodel_id, path)
        return JSONResponse(rendered, status_code=201, headers={"Location": element_url(request, path)})

    @router.post(elements, operation_id=operation_id("PostSubmodelElement"), status_code=201)
    async def post_element(
        request: Request,
        submodel: dict = Submodel,
        body: Dict[str, Any] = ELEMENT_BODY,
    ) -> JSONResponse:
        path, element = await editor(request).create_element(submodel["id"], "", body)
        return await created_element(request, submodel["id"], path, element)

    @router.post(element, operation_id=operation_id("PostSubmodelElementByPath"), status_code=201)
    async def post_element_by_path(
        request: Request,
        id_short_path: str,
        submodel: dict = Submodel,
        body: Dict[str, Any] = ELEMENT_BODY,
    ) -> JSONResponse:
        path, created = await editor(request).create_element(submodel["id"], id_short_path, body)
        return await created_element(request, submodel["id"], path, created)

    @router.put(element, operation_id=operation_id("PutSubmodelElementByPath"), status_code=204, response_class=Response)
    async def put_element(
        request: Request,
        id_short_path: str,
        submodel: dict = Submodel,
        body: Dict[str, Any] = ELEMENT_BODY,
    ) -> Response:
        created = await editor(request).put_element(submodel["id"], id_short_path, body)
        if not created:
            return Response(status_code=204)
        found = repository(request).get_submodel_element(submodel["id"], id_short_path)
        return await created_element(request, submodel["id"], id_short_path, found)

    @router.patch(element, operation_id=operation_id("PatchSubmodelElementByPath"), status_code=204, response_class=Response)
    async def patch_element(
        request: Request,
        id_short_path: str,
        submodel: dict = Submodel,
        level: Level = PATCH_LEVEL,
        body: Dict[str, Any] = ELEMENT_BODY,
    ) -> Response:
        check_patch_level(level)
        await editor(request).patch_element(submodel["id"], id_short_path, body, metadata_only=False)
        return Response(status_code=204)

    @router.patch(
        f"{element}/$metadata",
        operation_id=operation_id("PatchSubmodelElementByPath-Metadata"),
        status_code=204,
        response_class=Response,
    )
    async def patch_element_metadata(
        request: Request,
        id_short_path: str,
        submodel: dict = Submodel,
        body: Dict[str, Any] = ELEMENT_BODY,
    ) -> Response:
        await editor(request).patch_element(submodel["id"], id_short_path, body, metadata_only=True)
        return Response(status_code=204)

    @router.delete(element, operation_id=operation_id("DeleteSubmodelElementByPath"), status_code=204, response_class=Response)
    async def delete_element(request: Request, id_short_path: str, submodel: dict = Submodel) -> Response:
        await editor(request).delete_element(submodel["id"], id_short_path)
        return Response(status_code=204)

    # -------------------------------------------------------------------------
    # Invocação de Operations
    # -------------------------------------------------------------------------

    async def invoke_sync(request: Request, submodel: dict, id_short_path: str, body: dict, value_only: bool):
        found = repository(request).get_submodel_element(submodel["id"], id_short_path)
        call = invoker(request).prepare(found, submodel["id"], id_short_path, body, value_only)
        outcome = await invoker(request).execute(call, id_short_path)
        return outcome.render(value_only)

    async def invoke_async(request: Request, submodel: dict, id_short_path: str, body: dict, value_only: bool):
        found = repository(request).get_submodel_element(submodel["id"], id_short_path)
        call = invoker(request).prepare(
            found, submodel["id"], id_short_path, body, value_only, require_timeout=True
        )
        handle_id = invoker(request).start(call, submodel["id"], id_short_path, value_only)
        status_url = _sibling_url(request, "/invoke-async", f"/operation-status/{b64url_encode(handle_id)}")
        return JSONResponse({"handleId": handle_id}, status_code=202, headers={"Location": status_url})

    @router.post(f"{element}/invoke", operation_id=operation_id("InvokeOperation"))
    async def invoke_operation(
        request: Request,
        id_short_path: str,
        submodel: dict = Submodel,
        body: Dict[str, Any] = OPERATION_REQUEST,
    ) -> dict:
        return await invoke_sync(request, submodel, id_short_path, body, value_only=False)

    @router.post(f"{element}/invoke/$value", operation_id=operation_id("InvokeOperation-ValueOnly"))
    async def invoke_operation_value_only(
        request: Request,
        id_short_path: str,
        submodel: dict = Submodel,
        body: Dict[str, Any] = OPERATION_REQUEST,
    ) -> dict:
        return await invoke_sync(request, submodel, id_short_path, body, value_only=True)

    @router.post(
        f"{element}/invoke-async",
        operation_id=operation_id("InvokeOperationAsync"),
        status_code=202,
    )
    async def invoke_operation_async(
        request: Request,
        id_short_path: str,
        submodel: dict = Submodel,
        body: Dict[str, Any] = OPERATION_REQUEST,
    ) -> JSONResponse:
        return await invoke_async(request, submodel, id_short_path, body, value_only=False)

    @router.post(
        f"{element}/invoke-async/$value",
        operation_id=operation_id("InvokeOperationAsync-ValueOnly"),
        status_code=202,
    )
    async def invoke_operation_async_value_only(
        request: Request,
        id_short_path: str,
        submodel: dict = Submodel,
        body: Dict[str, Any] = OPERATION_REQUEST,
    ) -> JSONResponse:
        return await invoke_async(request, submodel, id_short_path, body, value_only=True)

    def async_invocation(request: Request, submodel: dict, id_short_path: str, handle_id: str):
        return invoker(request).get(b64url_decode(handle_id, what="handleId"), submodel["id"], id_short_path)

    @router.get(
        f"{element}/operation-status/{{handle_id}}",
        operation_id=operation_id("GetOperationAsyncStatus"),
    )
    async def get_operation_status(
        request: Request,
        id_short_path: str,
        handle_id: str,
        submodel: dict = Submodel,
    ) -> Any:
        invocation = async_invocation(request, submodel, id_short_path, handle_id)
        if invocation.outcome is None:
            return {"executionState": "Running"}
        # concluída: 302 para o resultado, na mesma forma em que foi invocada
        suffix = "/$value" if invocation.value_only else ""
        return RedirectResponse(
            _sibling_url(request, "/operation-status/", f"/operation-results/{handle_id}{suffix}"),
            status_code=302,
        )

    async def operation_result(request: Request, submodel: dict, id_short_path: str, handle_id: str, value_only: bool):
        invocation = async_invocation(request, submodel, id_short_path, handle_id)
        if invocation.outcome is None:
            return {"executionState": "Running"}
        return invocation.outcome.render(value_only)

    @router.get(
        f"{element}/operation-results/{{handle_id}}",
        operation_id=operation_id("GetOperationAsyncResult"),
    )
    async def get_operation_result(
        request: Request,
        id_short_path: str,
        handle_id: str,
        submodel: dict = Submodel,
    ) -> dict:
        return await operation_result(request, submodel, id_short_path, handle_id, value_only=False)

    @router.get(
        f"{element}/operation-results/{{handle_id}}/$value",
        operation_id=operation_id("GetOperationAsyncResult-ValueOnly"),
    )
    async def get_operation_result_value_only(
        request: Request,
        id_short_path: str,
        handle_id: str,
        submodel: dict = Submodel,
    ) -> dict:
        return await operation_result(request, submodel, id_short_path, handle_id, value_only=True)

    return router

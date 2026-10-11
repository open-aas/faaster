"""
Aplicação FastAPI da interface HTTP/REST do AAS (IDTA-01002-3-2).
"""
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from faaster.interfaces import IAddressSpace
from faaster.log import get_logger
from faaster.parser.aas_parser import AASParser
from faaster.parser.node_registry import NodeRegistry

from .editor import StructureEditor
from .errors import ApiError, result_body
from .operations import OperationInvoker
from .repository import AASRepository
from .routes import concept_descriptions, description, serialization, shells, submodels
from .serializer import AASSerializer
from .writer import ValueWriter


logger = get_logger(__name__)


def create_app(
    repository: AASRepository,
    registry: Optional[NodeRegistry] = None,
    base_path: str = "",
    address_space: Optional[IAddressSpace] = None,
    model_sync: Optional[AASParser] = None,
) -> FastAPI:
    """
    model_sync: parser que reflete no address space OPC UA as alterações
    estruturais feitas pela API (sem ele, só o modelo da API muda).
    """
    app = FastAPI(
        title="Faaster — AAS HTTP/REST API",
        description="Asset Administration Shell Part 2 API (IDTA-01002-3-2) servida pelo Faaster.",
        version="3.2",
        root_path_in_servers=False,
        openapi_url=f"{base_path}/openapi.json",
        docs_url=f"{base_path}/docs",
        redoc_url=None,
    )

    app.state.repository = repository
    app.state.serializer = AASSerializer(registry)
    app.state.writer = ValueWriter(registry)
    app.state.invoker = OperationInvoker(registry, address_space)
    app.state.editor = StructureEditor(repository, registry, model_sync)

    for module in (description, shells, submodels, concept_descriptions, serialization):
        app.include_router(module.router, prefix=base_path)

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(result_body(exc.status_code, exc.text), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        text = "; ".join(
            f"{'.'.join(str(p) for p in err.get('loc', []))}: {err.get('msg')}"
            for err in exc.errors()
        )
        return JSONResponse(result_body(400, text), status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(result_body(exc.status_code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("api.unexpected_error", path=request.url.path)
        return JSONResponse(result_body(500, "Internal server error"), status_code=500)

    return app

"""
Servidor HTTP da API AAS, executado no mesmo event loop do servidor OPC UA.

Compartilhar o loop permite ler e escrever os nós OPC UA e chamar seus
métodos diretamente, sem um cliente OPC UA intermediário.
"""
from typing import Optional

import uvicorn

from faaster.interfaces import IAddressSpace
from faaster.log import get_logger
from faaster.parser import AASParser, NodeRegistry

from .app import create_app
from .repository import AASRepository


logger = get_logger(__name__)


class HttpApiServer:
    def __init__(
        self,
        parser: AASParser,
        registry: NodeRegistry,
        host: str = "0.0.0.0",
        port: int = 8080,
        base_path: str = "/api/v3",
        address_space: Optional[IAddressSpace] = None,
    ) -> None:
        self._parser = parser
        self._address_space = address_space
        self._registry = registry
        self._host = host
        self._port = port
        self._base_path = base_path.rstrip("/")
        self._server: Optional[uvicorn.Server] = None
        self._app = None

    async def serve(self) -> None:
        """
        Sobe a API. Deve ser chamado após build_address_space(), quando o
        documento AAS e os nós de valor já estão disponíveis.
        """
        document = self._parser.document
        if document is None:
            logger.warning("http_api.skipped.no_document")
            return

        app = create_app(
            repository=AASRepository(document),
            registry=self._registry,
            base_path=self._base_path,
            address_space=self._address_space,
            model_sync=self._parser,
        )
        self._app = app

        config = uvicorn.Config(
            app,
            host=self._host,
            port=self._port,
            loop="none",        # reaproveita o loop (uvloop) já em execução
            lifespan="off",
            log_config=None,    # mantém o logging do Faaster (structlog)
            access_log=False,
        )
        self._server = uvicorn.Server(config)

        logger.info(
            "http_api.listening",
            url=f"http://{self._host}:{self._port}{self._base_path}",
        )
        await self._server.serve()

    def stop(self) -> None:
        if self._app is not None:
            # invocações assíncronas de Operations ainda em andamento
            self._app.state.invoker.cancel_all()
        if self._server is not None:
            self._server.should_exit = True

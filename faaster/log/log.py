from typing import Optional

import logging
import sys
import structlog


def configure_logging(debug: bool = False, log_file: Optional[str] = None) -> None:
    """
    Configura o structlog para o Faaster.

    Deve ser chamado uma única vez no entrypoint principal (main.py),
    antes de qualquer uso de logger.

    Em modo debug: nível DEBUG, formato colorido no console.
    Em modo produção: nível INFO, formato JSON — adequado para
    agregadores de log em borda (Loki, Datadog, etc).
    """
    level = logging.DEBUG if debug else logging.INFO

    # --- handlers stdlib ---
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        handlers=handlers,
        format="%(message)s",  # structlog cuida da formatação
    )

    # silencia libs verbosas em modo não-debug
    if not debug:
        logging.getLogger("asyncua").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)

    # --- processadores compartilhados ---
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    # --- renderer: JSON em produção, colorido em debug ---
    if debug:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    # structlog.configure(
    #     processors=shared_processors + [
    #         structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    #     ],
    #     logger_factory=structlog.stdlib.LoggerFactory(),
    #     wrapper_class=structlog.stdlib.BoundLogger,
    #     cache_logger_on_first_use=True,
    # )
    #
    # formatter = structlog.stdlib.ProcessorFormatter(
    #     processor=renderer,
    #     foreign_pre_chain=shared_processors,
    # )
    #
    # for handler in handlers:
    #     handler.setFormatter(formatter)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Retorna um logger structlog bound ao nome do módulo.

    Uso em qualquer módulo do Faaster:
        from core.log import get_logger
        logger = get_logger(__name__)
    """
    return structlog.get_logger(name)

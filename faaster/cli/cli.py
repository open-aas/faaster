from argparse import ArgumentParser, Namespace
from enum import Enum
from .cli_identification import make_identification_cli, resolve_build_date


class DatabaseBackend(str, Enum):
    mongodb = "mongodb"
    timescaledb = "timescaledb"

    def __str__(self) -> str:
        return self.value


def aas_parser_arguments() -> Namespace:
    parser = ArgumentParser(
        prog="faaster",
        description=(
            "Faaster — Framework for automated deployment of Reactive Asset "
            "Administration Shell (Type 2) over OPC UA."
        ),
        epilog=(
            "Examples:\n"
            "  faaster -m model.json --port 4840\n"
            "  faaster -m model.json --url-database mongodb://localhost:27017 --db-backend mongodb\n"
            "  faaster -m model.json --url-discovery opc.tcp://localhost:4840 --debug\n"
        ),
        formatter_class=__import__('argparse').RawDescriptionHelpFormatter
    )

    # -------------------------------------------------------------------------
    # Modelagem
    # -------------------------------------------------------------------------
    modeling = parser.add_argument_group("Modeling")
    modeling.add_argument(
        "-m", "--modeling-file",
        action="store",
        type=str,
        required=True,
        dest="modeling_file",
        metavar="PATH",
        help="Path to the AAS V3 JSON modeling file (required)."
    )
    # modeling.add_argument(
    #     "-cs", "--config-sensor",
    #     action="store",
    #     type=str,
    #     required=False,
    #     default=None,
    #     dest="config_sensor",
    #     metavar="PATH",
    #     help="Path to the sensor/event threshold configuration file (optional)."
    # )

    modeling.add_argument(
        "--aas_id_short",
        action="store",
        type=str,
        required=False,
        dest="aas_id_short",
        metavar="ID_SHORT",
        help="Id Short of the AAS  from modeling file",
        default="FaasterAASIdShort"
    )

    modeling.add_argument(
        "--aas_id",
        action="store",
        type=str,
        required=False,
        dest="aas_id",
        metavar="AAS_ID",
        help="Id unique of the AAS from modeling file",
        default="FaasterAASUniqueId"
    )

    # -------------------------------------------------------------------------
    # Servidor OPC UA
    # -------------------------------------------------------------------------
    server = parser.add_argument_group("OPC UA Server")
    server.add_argument(
        "--host",
        action="store",
        type=str,
        required=False,
        default="0.0.0.0",
        dest="host",
        metavar="HOST",
        help="Host address to bind the OPC UA server (default: 0.0.0.0)."
    )
    server.add_argument(
        "--port",
        action="store",
        type=int,
        required=False,
        default=4840,
        dest="port",
        metavar="PORT",
        help="Port to start listening OPC UA server (default: 4840)."
    )
    server.add_argument(
        "--url-discovery",
        action="store",
        type=str,
        required=False,
        default=None,
        dest="url_discovery",
        metavar="URL",
        help=(
            "OPC UA Local Discovery Service (LDS) URL for automatic registration "
            "(e.g. opc.tcp://localhost:4840)."
        )
    )

    # -------------------------------------------------------------------------
    # Banco de dados / HDA
    # -------------------------------------------------------------------------
    database = parser.add_argument_group("Historical Data Access (HDA)")
    database.add_argument(
        "--url-database",
        action="store",
        type=str,
        required=False,
        default=None,
        dest="url_database",
        metavar="URL",
        help=(
            "Connection URL of the time-series database backend used for HDA. "
            "MongoDB example: mongodb://user:pass@localhost:27017. "
            "TimescaleDB example: postgresql://user:pass@localhost:5432/dbname."
        )
    )
    database.add_argument(
        "--db-backend",
        action="store",
        type=DatabaseBackend,
        choices=list(DatabaseBackend),
        required=False,
        default=None,
        dest="db_backend",
        metavar="BACKEND",
        help=(
            f"Time-series database backend to use for HDA. "
            f"Choices: {', '.join(str(b) for b in DatabaseBackend)} "
            f"(default: inferred from --url-database scheme)."
        )
    )
    database.add_argument(
        "--db-name",
        action="store",
        type=str,
        required=False,
        default=None,
        dest="db_name",
        metavar="NAME",
        help=(
            "Database name to use for HDA storage. "
            "If not provided, the AAS idShort is used as the database name."
        )
    )

    # -------------------------------------------------------------------------
    # Mensageria / AMQP
    # -------------------------------------------------------------------------
    messaging = parser.add_argument_group("Messaging")
    messaging.add_argument(
        "--url-amqp",
        action="store",
        type=str,
        required=False,
        default=None,
        dest="url_amqp",
        metavar="URL",
        help=(
            "AMQP broker URL for event publishing (planned feature). "
            "Example: amqp://user:pass@localhost:5672."
        )
    )

    # -------------------------------------------------------------------------
    # Diagnóstico
    # -------------------------------------------------------------------------
    diagnostics = parser.add_argument_group("Diagnostics")
    diagnostics.add_argument(
        "--debug",
        action="store_true",
        required=False,
        default=False,
        dest="debug",
        help="Enable debug logging."
    )
    diagnostics.add_argument(
        "--log-file",
        action="store",
        type=str,
        required=False,
        default=None,
        dest="log_file",
        metavar="PATH",
        help="Path to write log output to a file (default: stdout only)."
    )
    diagnostics.add_argument(
        "--validate-only",
        action="store_true",
        required=False,
        default=False,
        dest="validate_only",
        help=(
            "Parse and validate the AAS modeling file against the V3 metamodel "
            "constraints (AASd) and exit without starting the OPC UA server. "
            "Useful for CI/CD pipelines."
        )
    )

    # -------------------------------------------------------------------------
    # Identificação (build_info OPC UA)
    # -------------------------------------------------------------------------
    arguments = make_identification_cli(parser)
    namespace = arguments.parse_args()
    namespace.build_date = resolve_build_date(namespace)

    _post_validate(namespace)
    return namespace


def _post_validate(args: Namespace) -> None:
    """
    Validações cruzadas entre argumentos que o argparse não consegue
    expressar de forma declarativa.
    """
    if args.url_database and args.db_backend is None:
        args.db_backend = _infer_backend(args.url_database)

    if args.db_backend is not None and args.url_database is None:
        raise SystemExit(
            "error: --db-backend requires --url-database to be specified."
        )


def _infer_backend(url: str) -> DatabaseBackend:
    """
    Infere o backend a partir do scheme da URL quando --db-backend
    não é fornecido explicitamente.

    mongodb://...      → DatabaseBackend.mongodb
    postgresql://...   → DatabaseBackend.timescaledb
    """
    url_lower = url.lower()

    if url_lower.startswith("mongodb"):
        return DatabaseBackend.mongodb

    if url_lower.startswith("postgresql") or url_lower.startswith("postgres"):
        return DatabaseBackend.timescaledb

    raise SystemExit(
        f"error: could not infer database backend from URL '{url}'. "
        f"Please specify --db-backend explicitly "
        f"({', '.join(str(b) for b in DatabaseBackend)})."
    )

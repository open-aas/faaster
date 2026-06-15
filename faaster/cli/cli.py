from argparse import ArgumentParser, Namespace
from enum import Enum
from .cli_identification import make_identification_cli, resolve_build_date
from faaster.security.server_security import SecurityPolicy, SecurityMode


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
        "--server-discovery",
        action="store",
        type=str,
        required=False,
        default=None,
        dest="server_discovery",
        metavar="URL",
        help=(
            "OPC UA Local Discovery Service (LDS) URL for automatic registration "
            "(e.g. opc.tcp://localhost:4840)."
        )
    )

    server.add_argument(
        '--discovery-url',
        action='store',
        type=str,
        required=False,
        default="opc.tcp://0.0.0.0/faaster/server",
        dest='discovery_url',
        metavar="URL",
        help=(
            "OPCUA external url inform to Local Discovery Service (LDS) "
            "default: opc.tcp://0.0.0.0/faaster/server"
        )
    )

    server.add_argument(
        "--gds-url",
        action="store",
        type=str,
        required=False,
        default=None,
        dest="gds_url",
        metavar="URL",
        help=(
            "Global Discovery Server (GDS) URL for application registration "
            "(e.g. opc.tcp://gds:58810). "
            "When provided, the server registers itself with the GDS on startup "
            "and periodically renews the registration (OPC 10000-12 §6.4)."
        )
    )

    server.add_argument(
        "--renew-interval",
        action="store",
        type=int,
        required=False,
        default=60,
        dest="renew_interval",
        metavar="INTERVAL",
        help=(
            "The duration of the renew discovery process"
        )
    )

    # -------------------------------------------------------------------------
    # Segurança — certificados e PKI
    # -------------------------------------------------------------------------
    security = parser.add_argument_group("Security")
    security.add_argument(
        "--pki-dir",
        action="store",
        type=str,
        required=False,
        default=None,
        dest="pki_dir",
        metavar="PATH",
        help=(
            "Directory for the OPC UA certificate store (PKI). "
            "Layout follows OPC 10000-12 Annex F: pki/own/, pki/trusted/, "
            "pki/issuers/, pki/rejected/. "
            "When provided, the server loads its certificate from this directory "
            "and manages it via the GDS (if --gds-url is also set)."
        )
    )
    security.add_argument(
        "--gds-username",
        action="store",
        type=str,
        required=False,
        default=None,
        dest="gds_username",
        metavar="USERNAME",
        help=(
            "Username for GDS authentication (OPC 10000-12 §7.2). "
            "Requires ApplicationSelfAdmin or DiscoveryAdmin role on the GDS."
        )
    )
    security.add_argument(
        "--gds-password",
        action="store",
        type=str,
        required=False,
        default=None,
        dest="gds_password",
        metavar="PASSWORD",
        help="Password for GDS authentication (used together with --gds-username)."
    )
    security.add_argument(
        "--cert-common-name",
        action="store",
        type=str,
        required=False,
        default=None,
        dest="cert_common_name",
        metavar="CN",
        help=(
            "Common Name (CN) for the OPC UA certificate. "
            "Defaults to the product name (--product-name). "
            "Example: \"Faaster AAS Server\"."
        )
    )
    security.add_argument(
        "--cert-san-dns",
        action="append",
        type=str,
        required=False,
        default=None,
        dest="cert_san_dns",
        metavar="DNS",
        help=(
            "DNS Subject Alternative Name for the certificate. "
            "Can be repeated: --cert-san-dns host1 --cert-san-dns host2."
        )
    )
    security.add_argument(
        "--cert-san-ip",
        action="append",
        type=str,
        required=False,
        default=None,
        dest="cert_san_ips",
        metavar="IP",
        help=(
            "IP Address Subject Alternative Name for the certificate. "
            "Can be repeated: --cert-san-ip 192.168.1.10 --cert-san-ip 10.0.0.1."
        )
    )
    security.add_argument(
        "--security-policy",
        action="append",
        type=SecurityPolicy,
        choices=list(SecurityPolicy),
        required=False,
        default=None,
        dest="security_policy",
        metavar="POLICY",
        help=(
            "OPC UA security policy to enable. Can be repeated to allow multiple policies. "
            f"Choices: basic256 (Basic256Sha256), aes128 (Aes128_Sha256_RsaOaep), "
            f"aes256 (Aes256_Sha256_RsaPss). "
            "Requires --pki-dir. Example: --security-policy basic256."
        )
    )
    security.add_argument(
        "--security-mode",
        action="store",
        type=SecurityMode,
        choices=list(SecurityMode),
        required=False,
        default=SecurityMode.sign_and_encrypt,
        dest="security_mode",
        metavar="MODE",
        help=(
            f"OPC UA security mode applied to all configured policies. "
            f"Choices: {', '.join(str(m) for m in SecurityMode)} "
            f"(default: {SecurityMode.sign_and_encrypt})."
        )
    )
    security.add_argument(
        "--allow-anonymous",
        action="store_true",
        required=False,
        default=False,
        dest="allow_anonymous",
        help=(
            "Keep a NoSecurity endpoint alongside secure ones, allowing clients "
            "without certificates to connect. Not recommended for production."
        )
    )
    security.add_argument(
        "--auto-accept-clients",
        action="store_true",
        required=False,
        default=False,
        dest="auto_accept_clients",
        help=(
            "Automatically trust any client certificate presented during connection "
            "(moves certs from pki/rejected/ to pki/trusted/ every 5 seconds). "
            "For development only — never use in production."
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

    if args.security_policy and not args.pki_dir:
        raise SystemExit(
            "error: --security-policy requires --pki-dir to be specified."
        )

    if args.auto_accept_clients and not args.pki_dir:
        raise SystemExit(
            "error: --auto-accept-clients requires --pki-dir to be specified."
        )

    if args.auto_accept_clients and not args.security_policy:
        raise SystemExit(
            "error: --auto-accept-clients only makes sense with --security-policy."
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

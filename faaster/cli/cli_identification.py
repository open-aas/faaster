from argparse import ArgumentParser
from datetime import datetime, timezone


def _default_build_date() -> str:
    """Retorna a data/hora UTC do momento do deploy em formato ISO 8601."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_package_version() -> str:
    """
    Tenta ler a versão do pacote instalado.
    Retorna '1.0.0' como fallback se não encontrar.
    """
    try:
        from importlib.metadata import version
        return version("faaster")
    except Exception:
        return "1.0.0"


def make_identification_cli(parser: ArgumentParser) -> ArgumentParser:
    """
    Adiciona ao parser os argumentos de identificação do servidor OPC UA,
    usados para compor o BuildInfo exposto pelo servidor.

    Todos os argumentos são opcionais — quando não fornecidos, assumem
    defaults razoáveis. Em ambientes de deploy automatizado, recomenda-se
    passar todos explicitamente via variáveis de ambiente ou flags do
    orquestrador.
    """
    group = parser.add_argument_group(
        "OPC UA Server Identity",
        description=(
            "Arguments used to populate the OPC UA BuildInfo node "
            "(ServerStatus > BuildInfo). These values are typically "
            "provided by the deployment system or the user."
        )
    )

    group.add_argument(
        "--product-uri",
        action="store",
        type=str,
        required=False,
        default="urn:faaster:server",
        dest="product_uri",
        metavar="URI",
        help=(
            "Product URI of the OPC UA server, exposed in BuildInfo. "
            "Should be a globally unique URN or URL identifying this "
            "deployment (default: urn:faaster:server)."
        )
    )

    group.add_argument(
        "--manufacturer-name",
        action="store",
        type=str,
        required=False,
        default="Faaster",
        dest="manufacturer_name",
        metavar="NAME",
        help="Name of the manufacturer, exposed in BuildInfo (default: Faaster)."
    )

    group.add_argument(
        "--product-name",
        action="store",
        type=str,
        required=False,
        default="Faaster Server",
        dest="product_name",
        metavar="NAME",
        help="Name of the product, exposed in BuildInfo (default: Faaster Server)."
    )

    group.add_argument(
        "--software-version",
        action="store",
        type=str,
        required=False,
        default=_get_package_version(),
        dest="software_version",
        metavar="VERSION",
        help=(
            "Software version of the server, exposed in BuildInfo. "
            "Defaults to the installed package version as reported by "
            "importlib.metadata (default: %(default)s)."
        )
    )

    group.add_argument(
        "--build-number",
        action="store",
        type=str,
        required=False,
        default="1",
        dest="build_number",
        metavar="NUMBER",
        help=(
            "Build number of the server, exposed in BuildInfo. "
            "In CI/CD pipelines, use the pipeline run ID here "
            "(default: 1)."
        )
    )

    group.add_argument(
        "--build-date",
        action="store",
        type=str,
        required=False,
        default=None,
        dest="build_date",
        metavar="DATETIME",
        help=(
            "Build/deploy date of the server in ISO 8601 format, exposed in BuildInfo. "
            "When not provided, defaults to the current UTC time at startup "
            "(e.g. 2026-04-16T14:30:00Z)."
        )
    )

    return parser


def resolve_build_date(args) -> str:
    """
    Resolve o build_date final a partir do Namespace parseado.
    Deve ser chamado após parse_args(), não durante a definição dos argumentos,
    para garantir que o timestamp reflita o momento real do deploy.

    Uso:
        args = aas_parser_arguments()
        args.build_date = resolve_build_date(args)
    """
    if args.build_date is not None:
        return args.build_date

    return _default_build_date()
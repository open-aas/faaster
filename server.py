import sys
from argparse import Namespace
from faaster.asset_administration_shell import AssetAdministrationShell
from faaster.cli import aas_parser_arguments
from faaster.log import configure_logging, get_logger

import asyncio
import signal
import uvloop

logger = get_logger(__name__)


async def validate_only(args: Namespace) -> int:
    """Validate model and extensions without starting the server (decision D15)."""
    from faaster.validation import validate

    report = await validate(args.modeling_file, args.sources_dir)
    print(report.to_json() if args.report_format == "json" else report.to_text())
    return 0 if report.ok else 1


async def main(args: Namespace):
    aas = AssetAdministrationShell(args)

    await aas.server.setup(args)
    await aas.server.build_address_space(args.modeling_file)
    await aas.server.init_hda()
    await aas.server.load_extension()

    # Ctrl+C / docker stop: encerra extensões, API, binding e HDA (que grava
    # as amostras pendentes) antes de sair
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(aas.server.stop()))

    await aas.server.run()


if __name__ == "__main__":
    # instantiates the parser object and informs a description
    args = aas_parser_arguments()
    # A JSON report owns stdout; logs go to stderr then.
    json_report = args.validate_only and args.report_format == "json"
    configure_logging(
        debug=args.debug, log_file=args.log_file, stream=sys.stderr if json_report else None
    )

    logger = get_logger(__name__)
    logger.info("faaster.starting")

    if args.validate_only:
        sys.exit(uvloop.run(validate_only(args)))
    uvloop.run(main(args))

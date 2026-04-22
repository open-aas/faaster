from argparse import Namespace
from faaster.asset_administration_shell import AssetAdministrationShell
from faaster.cli import aas_parser_arguments
from faaster.log import configure_logging, get_logger

import uvloop

logger = get_logger(__name__)


async def main(args: Namespace):
    aas = AssetAdministrationShell(args)

    if args.validate_only:
        return

    await aas.server.setup(args)
    await aas.server.build_address_space(args.modeling_file)
    await aas.server.init_hda()
    await aas.server.load_extension()
    await aas.server.run()


if __name__ == "__main__":
    # instantiates the parser object and informs a description
    args = aas_parser_arguments()
    configure_logging(debug=args.debug, log_file=args.log_file)

    logger = get_logger(__name__)
    logger.info("faaster.starting")

    uvloop.run(main(args))

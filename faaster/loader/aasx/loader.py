from pathlib import Path
from ..interfaces import ILoaderAasx
from ..exceptions import UnsupportedFormatLoaderError
from faaster.log import get_logger


logger = get_logger(__name__)


class AasxLoader(ILoaderAasx):
    """
    Placeholder para implementação futura do loader AASX.
    """

    async def load(self, path: Path) -> "Environment":
        raise UnsupportedFormatLoaderError(
            ".aasx (not yet implemented — use .json)"
        )

    async def extract(self, path: Path) -> Path:
        raise UnsupportedFormatLoaderError(
            ".aasx (not yet implemented — use .json)"
        )

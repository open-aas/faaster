from pathlib import Path
from ..interfaces import ILoaderXml
from ..exceptions import UnsupportedFormatLoaderError
from faaster.log import get_logger


logger = get_logger(__name__)


class XmlLoader(ILoaderXml):
    """
    Placeholder para implementação futura do loader XML.
    """

    async def load(self, path: Path) -> "Environment":
        raise UnsupportedFormatLoaderError(
            ".xml (not yet implemented — use .json)"
        )

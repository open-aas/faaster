from pathlib import Path
from .interfaces import ILoader
from .exceptions import UnsupportedFormatLoaderError
from faaster.log import get_logger
from .json.loader import JsonLoader
from .xml.loader import XmlLoader
from .aasx.loader import AasxLoader


logger = get_logger(__name__)


class LoaderFactory:
    """
    Detecta o formato do arquivo pela extensão e retorna
    a implementação correta de ILoader.
    """
    _SUPPORTED_EXTENSIONS = {".json", ".xml", ".aasx"}

    @staticmethod
    def create(path: str) -> ILoader:
        file_path = Path(path)
        extension = file_path.suffix.lower()

        logger.info(
            "loader.factory.create",
            path=str(file_path),
            extension=extension,
        )

        if extension == ".json":
            return JsonLoader()

        if extension == ".xml":
            return XmlLoader()

        if extension == ".aasx":
            return AasxLoader()

        raise UnsupportedFormatLoaderError(extension)

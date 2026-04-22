"""Resource represents an address to a file (a locator)."""

from typing import Optional
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.content_type import ContentType
from faaster.aas_metamodel.models.path_type import PathType


class Resource(DTO):
    """Resource represents an address to a file (a locator).

    The value is a URI that can represent an absolute or relative path.

    :param path: Path and name of the resource (with file extension).
    The path can be absolute or relative.
    :param content_type: Content type of the content of the file.
    The content type states which file extensions the file can have.
    """

    path: PathType
    content_type: Optional[ContentType] = None

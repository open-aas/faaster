"""Data Transfer Object for streaming file responses."""

from io import BytesIO
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.constrained_string import ConstrainedString


class StreamingResponseDTO(DTO):
    """Data Transfer Object for streaming file responses.

    :param file_content: The binary content of the file to be streamed.
    :param content_type: The MIME type indicating the nature of the file.
    :param content_disposition: Header to control how the content is handled.
    :param file_name: The name of the file for download or display purposes.
    """

    file_content: BytesIO
    content_type: ConstrainedString
    content_disposition: ConstrainedString
    file_name: ConstrainedString

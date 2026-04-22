"""Represents a file that is contained with its source code in the value attribute."""

from typing import Literal, Optional
from pydantic import Field
from faaster.aas_metamodel.models.blob_type import BlobType
from faaster.aas_metamodel.models.content_type import ContentType
from faaster.aas_metamodel.models.data_element import DataElement
from faaster.aas_metamodel.models.model_type import ModelType


class Blob(DataElement):
    """Represents a file that is contained with its source code in the value attribute.

    :param value: The value of the BLOB instance of a blob data element.
    :type value: BlobType
    :param content_type: Content type of the content of the BLOB.
    The content type (MIME type) states which file extensions the file can have.
    Valid values are content types like e.g. "application.json", "application/xls", "image/jpg".
    """

    type_model: Literal[ModelType.BLOB] = Field(alias="modelType", default=ModelType.BLOB)
    value: Optional[BlobType] = None
    content_type: ContentType

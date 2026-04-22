"""A File is a data element that represents an address to a file (a locator)."""

from typing import Literal, Optional
from pydantic import Field, model_validator
from faaster.aas_metamodel.models.content_type import ContentType
from faaster.aas_metamodel.models.data_element import DataElement
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.path_type import PathType


class File(DataElement):
    """A File is a data element that represents an address to a file (a locator).

    The value is a URI that can represent an absolute or relative path.

    :param value: Path and name of the file (with file extension).
    The path can be absolute or relative.
    :param content_type: Content type of the content of the file.
    The content type states which file extensions the file can have.
    """

    type_model: Literal[ModelType.FILE] = Field(alias="modelType", default=ModelType.FILE)
    value: Optional[PathType] = None
    content_type: ContentType

    @model_validator(mode="before")
    @classmethod
    def ensure_file_model_type(cls, values: dict) -> dict:
        """Reject payloads whose modelType is not 'File'."""
        model_type = values.get("modelType") or values.get("type_model")

        if model_type is not None and model_type != ModelType.FILE:
            raise ValueError("Not a File element")

        return values

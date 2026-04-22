from datetime import datetime
from typing import Any

from bson.objectid import ObjectId
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


def to_camel_without_underscore(v: str):
    """Convert a string to camelCase and remove underscores."""
    camel = to_camel(v)
    return camel.replace("_", "")


def exclude_empty_lists(model_dict):
    """Remove keys from a dictionary where the value is an empty list or dictionary."""
    return {
        key: value
        for key, value in model_dict.items()
        if not (isinstance(value, (list, dict)) and not value)
    }


class DTO(BaseModel):
    """Base Data Transfer Object (DTO) class with custom serialization logic."""

    model_config = ConfigDict(
        strict=False,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        alias_generator=to_camel_without_underscore,
        json_encoders={
            datetime: lambda v: v.isoformat().replace("+00:00", "Z"),
            # ShortName: attrgetter("name"),
            ObjectId: str,
        },
    )

    def model_dump(self, exclude_none=False, **kwargs) -> dict[str, Any]:
        """Serialize the DTO to a dictionary.

        :param exclude_none: If True, remove keys with None values or empty lists/dictionaries,
        by default False.
        :returns: Serialized dictionary representation of the DTO.
        """
        data = super().model_dump(**kwargs)

        if exclude_none:
            return exclude_empty_lists(data)

        return data

    def __init__(self, **attrs):
        """Initialize the DTO, converting ObjectId fields to strings if present.

        :param attrs: Attribute values for the model.
        """
        if "_id" in attrs and isinstance(attrs["_id"], ObjectId):
            attrs["_id"] = str(attrs["_id"])

        super().__init__(**attrs)

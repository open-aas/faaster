"""DTO representing an Embedded Data Specification with optional reference and content."""

from typing import Optional

from pydantic import field_validator
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.data_specification_iec_61360 import DataSpecificationIec61360
from faaster.aas_metamodel.models.lang_string_set import LangStringSet
from faaster.aas_metamodel.models.reference import Reference


# DataSpecificationContent is a mandatory parameter!
class EmbeddedDataSpecification(DTO):
    """DTO representing an Embedded Data Specification with optional reference and content."""

    data_specification: Optional[Reference] = None
    data_specification_content: Optional[DataSpecificationIec61360] = None

    @field_validator("data_specification_content", mode="before")
    @classmethod
    def set_default_data_specification_content(cls, value):
        """Ensure that data_specification_content is a valid DataSpecificationIec61360.

        Setting defaults when none are provided.

        :param cls: The model class where the validator is applied.
        :param value: The provided value for data_specification_content.
        :return: A DataSpecificationIec61360 instance or a normalized dictionary.
        """
        if value is None:
            return DataSpecificationIec61360(
                type_model="DataSpecificationIec61360",
                preferred_name=[LangStringSet(language="en-US", text="default")],
            )

        if isinstance(value, dict):
            if not value.get("preferred_name"):
                value["preferred_name"] = [{"language": "en-US", "text": "default"}]
            value["type_model"] = "DataSpecificationIec61360"

        return value

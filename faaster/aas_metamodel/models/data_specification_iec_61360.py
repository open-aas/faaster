"""Content of data specification template."""

from typing import Optional
from pydantic import field_validator
from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.models.data_specification_content import DataSpecificationContent
from faaster.aas_metamodel.models.data_type_iec_61360 import DataTypeIEC61360
from faaster.aas_metamodel.models.definition_type_iec_61360 import DefinitionTypeIEC61360
from faaster.aas_metamodel.models.level_type import LevelType
from faaster.aas_metamodel.models.preferred_name_type_iec_61360 import PreferredNameTypeIEC61360
from faaster.aas_metamodel.models.reference import Reference
from faaster.aas_metamodel.models.short_name_type_iec_61360 import ShortNameTypeIEC61360
from faaster.aas_metamodel.models.value_list import ValueList
from faaster.aas_metamodel.exceptions import InvalidFieldException


class DataSpecificationIec61360(DataSpecificationContent):
    """Content of data specification template.

    For concept descriptions for properties, values and value lists conformant to IEC 61360.

    :param preferred_name: Preferred name.
    :param short_name: Short name.
    :param unit: Unit.
    :param unit_id: Unique ID.
    :param source_of_definition: Source of definition.
    :param symbol: Symbol.
    :param data_type: Data Type.
    :param definition: Definition in different languages.
    :param value_format: Value Format.
    :param value_list: List of allowed values.
    :param value: Value.
    :param level_type: Set of levels.
    """

    preferred_name: PreferredNameTypeIEC61360
    short_name: Optional[ShortNameTypeIEC61360] = []
    unit: Optional[ConstrainedString] = None
    unit_id: Optional[Reference] = None
    source_of_definition: Optional[ConstrainedString] = None
    symbol: Optional[ConstrainedString] = None
    data_type: Optional[DataTypeIEC61360] = None
    definition: Optional[DefinitionTypeIEC61360] = []
    value_format: Optional[ConstrainedString] = None  # ValueFormatTypeIec61360
    value_list: Optional[ValueList] = None
    value: Optional[ConstrainedString] = None  # ValueTypeIec61360
    level_type: Optional[LevelType] = None

    @field_validator("preferred_name")
    @classmethod
    def validate_preferred_name(cls, value: PreferredNameTypeIEC61360) -> PreferredNameTypeIEC61360:
        """Validate preferredName according to IEC61360 + AASc-002."""
        if not value:
            raise InvalidFieldException(
                detail="preferredName must contain at least one entry with language 'en' "
                "(Constraint AASc-002)."
            )

        langs = {
            (entry.language.split("-")[0].lower()) for entry in value if entry and entry.language
        }

        if "en" not in langs:
            raise InvalidFieldException(
                detail=(
                    "preferredName must include at least one entry with language 'en' "
                    "(Constraint AASc-002)."
                )
            )

        for entry in value:
            if entry is None:
                continue

            text = entry.text

            if text is None or text.strip() == "":
                raise InvalidFieldException(
                    detail=f"preferredName text must not be empty "
                    f"for language '{entry.language}'."
                )

            if len(text) < 1:
                raise InvalidFieldException(
                    detail=f"preferredName text must have at least 1 character "
                    f"(language '{entry.language}')."
                )

            if len(text) > 255:
                raise InvalidFieldException(
                    detail=(
                        f"preferredName text exceeds the maximum allowed length of 255 characters "
                        f"(given length: {len(text)}), language '{entry.language}'."
                    )
                )

        return value

    @field_validator("short_name")
    @classmethod
    def validate_short_name(
        cls, value: Optional[ShortNameTypeIEC61360]
    ) -> Optional[ShortNameTypeIEC61360]:
        """Ensure each short_name entry (if provided) has a non-empty text and max length=18."""
        if not value:
            return value

        for entry in value:
            if entry is None:
                continue

            text = entry.text

            # Empty check
            if text is None or text.strip() == "":
                raise InvalidFieldException(
                    detail=(
                        "Short name text must not be empty " f"for language '{entry.language}'."
                    )
                )

            # IEC 61360 constraint: maximum length = 18
            if len(text) > 18:
                raise InvalidFieldException(
                    detail=(
                        f"Short name text exceeds the maximum allowed length of 18 characters "
                        f"(given length: {len(text)}), text: '{text}'."
                    )
                )

        return value

    @field_validator("definition")
    @classmethod
    def validate_language(
        cls, value: Optional[DefinitionTypeIEC61360]
    ) -> Optional[DefinitionTypeIEC61360]:
        """Validate that each definition entry has a non-empty text.

        :param cls: The model class where the validator is applied.
        :param value: The list of definition entries.
        :return: The validated list of definition entries.
        :raises InvalidFieldException: If any definition text is empty.
        """
        if not value:
            return value

        for entry in value:
            if entry is None:
                continue

            text = entry.text
            if text is None or text.strip() == "":
                raise InvalidFieldException(
                    detail=(
                        "Definition text must not be empty " f"for language '{entry.language}'."
                    )
                )

            # IEC 61360 constraint: maximum length = 1023
            if len(text) > 1023:
                raise InvalidFieldException(
                    detail=(
                        f"Definition text exceeds the maximum allowed length of 1023 characters "
                        f"(given length: {len(text)}), text: '{text}'."
                    )
                )

        return value

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: Optional[ConstrainedString]) -> Optional[ConstrainedString]:
        """Validate IEC 61360 value string length (1 to 2000 characters)."""
        if value is None:
            return value  # value é opcional na IEC 61360

        text = value.strip()

        # Mínimo de 1
        if len(text) < 1:
            raise InvalidFieldException(
                detail="Value must contain at least 1 character (IEC 61360, minLength=1)."
            )

        # Máximo de 2000
        if len(text) > 2000:
            raise InvalidFieldException(
                detail=(
                    f"Value exceeds maximum allowed length of 2000 characters "
                    f"(given length: {len(text)})."
                )
            )

        return value

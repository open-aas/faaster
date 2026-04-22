from basyx.aas import model
from basyx.aas.model.datatypes import XSD_TYPE_CLASSES
from faaster.aas_metamodel.exceptions import InvalidFieldException


def validate_value_type(value: str, value_type_str: str) -> None:
    """Validate a value against an AAS XSD value type.

    Uses BaSyx datatypes to enforce constraints.

    :param value: The value to validate.
    :param value_type_str: The XSD type string (e.g. "xs:int", "xs:boolean").
    :raises InvalidFieldException: If the type is unsupported or conversion fails.
    """
    value_type_class = XSD_TYPE_CLASSES.get(value_type_str)

    if value_type_class is None:
        valid_types = ", ".join(XSD_TYPE_CLASSES.keys())
        raise InvalidFieldException(
            detail=(
                f"Invalid valueType '{value_type_str}' for value '{value}'. "
                f"Supported types are: {valid_types}"
            )
        )

    try:
        model.datatypes.from_xsd(value, type_=value_type_class)
    except ValueError as e:
        raise InvalidFieldException(
            detail=(
                f"Error converting '{value}' to type '{value_type_str}' "
                f"(Constraint AASd-020): {e}."
            )
        ) from e

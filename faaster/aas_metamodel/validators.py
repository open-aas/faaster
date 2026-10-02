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


def validate_children_id_short(elements, container: str) -> None:
    """Constraint AASd-117.

    idShort of non-identifiable Referables not being a direct child of a
    SubmodelElementList shall be specified. Containers other than
    SubmodelElementList call this for their direct children.

    :param elements: Child elements (model instances or serialized dicts).
    :param container: Name of the container, used in the error message.
    :raises InvalidFieldException: If a child has no idShort.
    """
    for index, elem in enumerate(elements or []):
        if isinstance(elem, dict):
            id_short = elem.get("idShort") or elem.get("id_short")
        else:
            id_short = getattr(elem, "id_short", None)
        if not id_short:
            raise InvalidFieldException(
                detail=(
                    f"Element at position {index} of {container} has no idShort. "
                    "idShort is mandatory for all Referables except direct children "
                    "of a SubmodelElementList (Constraint AASd-117)."
                )
            )

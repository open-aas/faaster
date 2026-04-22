"""Reference to either a model element of the same or another AAS or to an external entity."""

from typing import List
from pydantic import model_validator
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.key import Key
from faaster.aas_metamodel.models.key_types import KeyTypes
from faaster.aas_metamodel.models.reference_types import ReferenceTypes
from faaster.aas_metamodel.exceptions import InvalidFieldException


import structlog


logger = structlog.get_logger(__name__)


class ReferenceParent(DTO):
    """Reference to either a model element of the same or another AAS or to an external entity.

    A reference is an ordered list of keys.
    A model reference is an ordered list of keys, each key referencing an element.
    The complete list of keys may for example be concatenated to a path that then
    gives unique access to an element.
    A global reference is a reference to an external entity.

    :param type: Type of the reference. Denotes, whether reference is a global reference or
    a model reference.
    :param keys: Unique reference in its name space.
    """

    type: ReferenceTypes
    keys: List[Key]

    @model_validator(mode="after")
    def validate_constraints(self) -> "ReferenceParent":
        """Validate constraints AASd-121 to AASd-128."""
        list_keys = self.keys
        if list_keys:
            if list_keys[0].type not in Key.GLOBALLY_IDENTIFIABLES:
                logger.error(f"Invalid first key type for reference: {list_keys}")

                raise InvalidFieldException(
                    detail="For References, the value of Key/type of the first key of "
                    "Reference/keys shall be one of GloballyIdentifiables (Constraint "
                    "AASd-121)."
                )

            # External Reference
            if self.type == ReferenceTypes.GLOBAL_REFERENCE:
                if list_keys[0].type not in Key.GENERIC_GLOBALLY_IDENTIFIABLES:
                    logger.error(f"Invalid first key type for global reference: {list_keys}")

                    raise InvalidFieldException(
                        detail="For external references, i.e. References with Reference/type = "
                        "ExternalReference, the value of Key/type of the first key of "
                        "Reference/keys shall be one of GenericGloballyIdentifiables ("
                        "Constraint AASd-122)."
                    )

                if (
                    list_keys[-1].type
                    not in Key.GENERIC_GLOBALLY_IDENTIFIABLES | Key.GENERIC_FRAGMENT_KEYS
                ):
                    logger.error(f"Invalid last key type for global reference: {list_keys}")

                    raise InvalidFieldException(
                        detail="For external references, i.e. References with Reference/type = "
                        "ExternalReference, the last key of Reference/keys shall be either "
                        "one of GenericGloballyIdentifiables or one of GenericFragmentKeys "
                        "(Constraint AASd-124)."
                    )

            # Model Reference
            if self.type == ReferenceTypes.MODEL_REFERENCE:
                if list_keys[0].type not in Key.AAS_IDENTIFIABLES:
                    logger.error(f"Invalid first key type for model reference: {list_keys}")

                    raise InvalidFieldException(
                        detail="For model references, i.e. References with Reference/type = "
                        "ModelReference, the value of Key/type of the first key of "
                        "Reference/keys shall be one of AasIdentifiables (Constraint "
                        "AASd-123)."
                    )

                if len(list_keys) > 1:
                    for key in list_keys[1:]:
                        if key.type not in Key.FRAGMENT_KEYS:
                            logger.error(f"Invalid key type for model reference: {list_keys}")

                            raise InvalidFieldException(
                                detail="For model references, i.e. References with Reference/type "
                                "= ModelReference with more than one key in "
                                "Reference/keys, the value of Key/type of each of the keys "
                                "following the first key of Reference/keys shall be one of "
                                "FragmentKeys. (Constraint AASd-125)."
                            )

                if len(list_keys) > 1 and any(
                    key.type in Key.GENERIC_FRAGMENT_KEYS for key in list_keys[:-1]
                ):
                    logger.error(f"Invalid key type for model reference: {list_keys}")
                    raise InvalidFieldException(
                        detail="For model references, i.e. References with Reference/type = "
                        "ModelReference with more than one key in Reference/keys, "
                        "the value of Key/type of the last Key in the reference key chain "
                        "may be one of GenericFragmentKeys, or no key at all shall have a "
                        "value out of GenericFragmentKeys (Constraint AASd-126)"
                    )

                if len(list_keys) > 1:
                    for i, key in enumerate(list_keys[1:], start=1):
                        if key.type == KeyTypes.FRAGMENT_REFERENCE and list_keys[
                            i - 1
                        ].type not in {KeyTypes.FILE, KeyTypes.BLOB}:
                            logger.error(f"Invalid key type for model reference: {list_keys}")
                            raise InvalidFieldException(
                                detail="For model references, i.e. References with Reference/type "
                                "= ModelReference with more than one key in "
                                "Reference/keys, a key with Key/type FragmentReference "
                                "shall be preceded by a key with Key/type File or Blob. "
                                "All other AAS fragments, i.e. Key/type values out of "
                                "AasSubmodelElements, do not support fragments (Constraint "
                                "AASd-127)."
                            )

                if len(list_keys) > 1:
                    for i, key in enumerate(list_keys[1:], start=1):
                        if list_keys[i - 1].type == KeyTypes.SUBMODEL_ELEMENT_LIST:
                            if isinstance(key.value, str):
                                if not key.value.isdigit():
                                    logger.error(f"Invalid key value for model reference: {list_keys}")
                                    raise InvalidFieldException(
                                        detail="For model references, i.e. References with "
                                        "Reference/type = ModelReference, the Key/value of a "
                                        "Key preceded by a Key with "
                                        "Key/type=SubmodelElementList is an integer number "
                                        "denoting the position in the array of the submodel "
                                        "element list (Constraint AASd-128)."
                                    )

        return self

"""A key is a reference to an element by its ID."""

from typing import ClassVar
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.identifier import Identifier
from faaster.aas_metamodel.models.key_types import KeyTypes


class Key(DTO):
    """A key is a reference to an element by its ID.

    :param type: Denotes which kind of entity is referenced.
    In case type = FragmentId the key represents a bookmark or a similar local identifier within its
    parent element as specified by the key that precedes this key.
    In all other cases the key references a model element of the same or of another AAS. The name
    of the model element is explicitly listed.
    :param value: The key value, for example an IRDI or a URI.
    """

    type: KeyTypes
    value: Identifier

    GLOBALLY_IDENTIFIABLES: ClassVar[set] = {
        KeyTypes.ASSET_ADMINISTRATION_SHELL,
        KeyTypes.CONCEPT_DESCRIPTION,
        KeyTypes.IDENTIFIABLE,
        KeyTypes.SUBMODEL,
        KeyTypes.GLOBAL_REFERENCE,
    }

    GENERIC_GLOBALLY_IDENTIFIABLES: ClassVar[set] = {
        KeyTypes.GLOBAL_REFERENCE,
    }

    AAS_IDENTIFIABLES: ClassVar[set] = {
        KeyTypes.ASSET_ADMINISTRATION_SHELL,
        KeyTypes.CONCEPT_DESCRIPTION,
        KeyTypes.IDENTIFIABLE,
        KeyTypes.SUBMODEL,
    }

    GENERIC_FRAGMENT_KEYS: ClassVar[set] = {
        KeyTypes.FRAGMENT_REFERENCE,
    }

    FRAGMENT_KEYS: ClassVar[set] = {
        KeyTypes.FRAGMENT_REFERENCE,
        KeyTypes.REFERABLE,
        KeyTypes.ANNOTATED_RELATIONSHIP_ELEMENT,
        KeyTypes.BASIC_EVENT_ELEMENT,
        KeyTypes.BLOB,
        KeyTypes.CAPABILITY,
        KeyTypes.DATA_ELEMENT,
        KeyTypes.ENTITY,
        KeyTypes.EVENT_ELEMENT,
        KeyTypes.FILE,
        KeyTypes.MULTI_LANGUAGE_PROPERTY,
        KeyTypes.OPERATION,
        KeyTypes.PROPERTY,
        KeyTypes.RANGE,
        KeyTypes.REFERENCE_ELEMENT,
        KeyTypes.RELATIONSHIP_ELEMENT,
        KeyTypes.SUBMODEL_ELEMENT,
        KeyTypes.SUBMODEL_ELEMENT_COLLECTION,
        KeyTypes.SUBMODEL_ELEMENT_LIST,
    }

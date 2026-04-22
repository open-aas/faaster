"""Enumeration of different key value types within a key."""

# pylint: disable=duplicate-code

from enum import Enum


class KeyTypes(str, Enum):
    """Enumeration of different key value types within a key.

    :param GLOBAL_REFERENCE: Global reference.
    :param ASSET_ADMINISTRATION_SHELL: Asset Administration Shell.
    :param CONCEPT_DESCRIPTION: Concept Description.
    :param IDENTIFIABLE: Identifiable.
    :param SUBMODEL: Submodel.
    :param REFERABLE: Referable.
    :param ANNOTATED_RELATIONSHIP_ELEMENT: Annotated relationship element.
    :param BASIC_EVENT_ELEMENT: Basic event element.
    :param BLOB: Blob.
    :param CAPABILITY: Capability.
    :param DATA_ELEMENT: Data element.
    :param ENTITY: Entity.
    :param EVENT_ELEMENT: Event.
    :param FILE: File.
    :param MULTI_LANGUAGE_PROPERTY: Property with a value that can be provided in
    multiple languages.
    :param PROPERTY: Property.
    :param OPERATION: Operation.
    :param RANGE: Range with min and max.
    :param RELATIONSHIP_ELEMENT: Relationship.
    :param REFERENCE_ELEMENT: Reference.
    :param SUBMODEL_ELEMENT: Submodel element.
    :param SUBMODEL_ELEMENT_COLLECTION: Struct of submodel elements.
    :param SUBMODEL_ELEMENT_LIST: List of submodel elements.
    :param FRAGMENT_REFERENCE: Bookmark or a similar local identifier of a subordinate
    part of a primary resource.
    """

    # AAS Identifiables
    ASSET_ADMINISTRATION_SHELL = "AssetAdministrationShell"
    CONCEPT_DESCRIPTION = "ConceptDescription"
    IDENTIFIABLE = "Identifiable"
    SUBMODEL = "Submodel"

    # Generic Globally Identifiables
    GLOBAL_REFERENCE = "GlobalReference"

    # Globally Identifiables inherits from AAS Identifiables and Generic Globally Identifiables

    # AAS Submodel Elements
    ANNOTATED_RELATIONSHIP_ELEMENT = "AnnotatedRelationshipElement"
    BASIC_EVENT_ELEMENT = "BasicEventElement"
    BLOB = "Blob"
    CAPABILITY = "Capability"
    DATA_ELEMENT = "DataElement"
    ENTITY = "Entity"
    EVENT_ELEMENT = "EventElement"
    FILE = "File"
    MULTI_LANGUAGE_PROPERTY = "MultiLanguageProperty"
    OPERATION = "Operation"
    PROPERTY = "Property"
    RANGE = "Range"
    REFERENCE_ELEMENT = "ReferenceElement"
    RELATIONSHIP_ELEMENT = "RelationshipElement"
    SUBMODEL_ELEMENT = "SubmodelElement"
    SUBMODEL_ELEMENT_COLLECTION = "SubmodelElementCollection"
    SUBMODEL_ELEMENT_LIST = "SubmodelElementList"

    # AAS Referable Non Identifiables (inherits from AAS Submodel Elements)
    REFERABLE = "Referable"

    # Generic Fragment Keys
    FRAGMENT_REFERENCE = "FragmentReference"

    # Fragment Keys (inherits from Generic Fragment Keys and AAS Referable Non Identifiables)

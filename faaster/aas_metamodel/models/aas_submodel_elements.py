"""Enumeration of different fragment key value types within a key."""

# pylint: disable=duplicate-code

from enum import Enum


class AasSubmodelElements(str, Enum):
    """Enumeration of different fragment key value types within a key.

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
    """

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

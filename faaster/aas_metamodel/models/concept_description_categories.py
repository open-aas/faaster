"""Categories of concept descriptions."""

from enum import Enum


class ConceptDescriptionCategories(str, Enum):
    """Categories of concept descriptions."""

    APPLICATION_CLASS = "APPLICATION_CLASS"
    CAPABILITY = "CAPABILITY"
    COLLECTION = "COLLECTION"
    DOCUMENT = "DOCUMENT"
    ENTITY = "ENTITY"
    EVENT = "EVENT"
    FUNCTION = "FUNCTION"
    PROPERTY = "PROPERTY"
    VALUE = "VALUE"
    RANGE = "RANGE"
    QUALIFIER_TYPE = "QUALIFIER_TYPE"
    REFERENCE = "REFERENCE"
    RELATIONSHIP = "RELATIONSHIP"

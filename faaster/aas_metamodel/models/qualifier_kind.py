"""Enumeration for kinds of qualifiers."""

from enum import Enum


class QualifierKind(str, Enum):
    """Enumeration for kinds of qualifiers.
    \f
    :param VALUE_QUALIFIER: Qualifies the value of the element and can change during run-time.
    Value qualifiers are only applicable to elements with kind="Instance".
    :param CONCEPT_QUALIFIER: Qualifiers the semantic definition the element is referring to.
    :param TEMPLATE_QUALIFIER: Qualifies the element within a specific submodel on concept level.
    Template qualifiers are only applicable to elements with kind="Template".
    """

    VALUE_QUALIFIER = "ValueQualifier"
    CONCEPT_QUALIFIER = "ConceptQualifier"
    TEMPLATE_QUALIFIER = "TemplateQualifier"

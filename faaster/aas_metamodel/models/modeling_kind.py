"""Enumeration for denoting whether an element is a template or an instance."""

from enum import Enum


class ModelingKind(str, Enum):
    """Enumeration for denoting whether an element is a template or an instance.

    :param TEMPLATE: Software element which specifies the common attributes shared by
    all instances of the element of the template.
    :param INSTANCE: Concrete, clearly identifiable component of a certain template.
    """

    TEMPLATE = "Template"
    INSTANCE = "Instance"

"""Enumeration of RDF built-in types used in AAS models."""

from enum import Enum


class RdfBuildInTypes(str, Enum):
    """RDF built-in types supported for serialization."""

    LANG_STRING = "rdf:langString"

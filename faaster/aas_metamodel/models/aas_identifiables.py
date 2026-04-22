"""Enumeration of different key value types within a key."""

from enum import Enum


class AasIdentifiables(str, Enum):
    """Enumeration of different key value types within a key."""

    ASSET_ADMINISTRATION_SHELL = "AssetAdministrationShell"
    CONCEPT_DESCRIPTION = "ConceptDescription"
    IDENTIFIABLE = "Identifiable"
    SUBMODEL = "Submodel"

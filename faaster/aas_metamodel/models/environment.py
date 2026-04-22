"""Container for the sets of different identifiables."""

from typing import List, Optional
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.asset_administration_shell import AssetAdministrationShell
from faaster.aas_metamodel.models.concept_description import ConceptDescription
from faaster.aas_metamodel.models.submodel import Submodel


class Environment(DTO):
    """Container for the sets of different identifiables.

    :param asset_administration_shells: Asset administration shell.
    :param submodels: Submodel.
    :param concept_descriptions: Concept description.
    """

    asset_administration_shells: Optional[List[AssetAdministrationShell]] = []
    submodels: Optional[List[Submodel]] = []
    concept_descriptions: Optional[List[ConceptDescription]] = []

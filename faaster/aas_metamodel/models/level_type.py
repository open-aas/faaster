"""The Level Type of DataSpecificationIec61360 element."""

from faaster.aas_metamodel.dto import DTO


class LevelType(DTO):
    """The Level Type of DataSpecificationIec61360 element."""

    min: bool
    max: bool
    nom: bool
    typ: bool

"""Data specification content choice."""

from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.data_specification_iec_61360 import DataSpecificationIec61360


class DataSpecificationContentChoice(DTO):
    """Data specification content choice."""

    one_of: DataSpecificationIec61360

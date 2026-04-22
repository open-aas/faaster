"""Content of data specification template for concept descriptions."""

from typing import Optional
from faaster.aas_metamodel.models.constrained_string import ConstrainedString
from faaster.aas_metamodel.models.data_specification_content import DataSpecificationContent
from faaster.aas_metamodel.models.lang_string_set import LangStringSet


class DataSpecificationPhysicalUnit(DataSpecificationContent):
    """Content of data specification template for concept descriptions.

    For physical units conformant to IEC 61360.

    :param unit_name: Name of the physical unit.
    :param unit_symbol: Symbol for the physical unit.
    :param definition: Definition in different languages.
    :param si_notation: Notation of SI physical unit.
    :param si_name: Name of SI physical unit.
    :param din_notation: Notation of physical unit conformant to DIN.
    :param ece_name: Name of physical unit conformant to ECE.
    :param ece_code: Code of physical unit conformant to ECE.
    :param nist_name: Name of NIST physical unit.
    :param source_of_definition: Source of definition.
    :param conversion_factor: Conversion factor.
    :param registration_authority_id: Registration authority ID.
    :param supplier: Supplier.
    """

    unit_name: ConstrainedString
    unit_symbol: ConstrainedString
    definition: LangStringSet
    si_notation: Optional[ConstrainedString]
    si_name: Optional[ConstrainedString]
    din_notation: Optional[ConstrainedString]
    ece_name: Optional[ConstrainedString]
    ece_code: Optional[ConstrainedString]
    nist_name: Optional[ConstrainedString]
    source_of_definition: Optional[ConstrainedString]
    conversion_factor: Optional[ConstrainedString]
    registration_authority_id: Optional[ConstrainedString]
    supplier: Optional[ConstrainedString]

"""Data Specification Template."""

from typing import Optional
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.administrative_information import AdministrativeInformation
from faaster.aas_metamodel.models.data_specification_content import DataSpecificationContent
from faaster.aas_metamodel.models.identifier import Identifier
from faaster.aas_metamodel.models.lang_string_set import LangStringSet


class DataSpecification(DTO):
    """Data Specification Template.

    :param administration: Administrative information of an identifiable element.
    :param id: The globally unique identification of the element.
    :param data_specification_content: The content of the template without metadata.
    :param description: Description how and in which context the data specification template
    is applicable. The description can be provided in several languages.
    """

    administration: Optional[AdministrativeInformation]
    id: Identifier
    data_specification_content: DataSpecificationContent
    description: Optional[LangStringSet] = None

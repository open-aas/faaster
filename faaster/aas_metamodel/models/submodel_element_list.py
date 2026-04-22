"""A submodel element list is an ordered list of submodel elements."""

# pylint: disable=duplicate-code

from typing import List, Literal, Optional
from pydantic import Field
from faaster.aas_metamodel.submodel_element_processor import SubmodelElementProcessor
from faaster.aas_metamodel.models.aas_submodel_elements import AasSubmodelElements
from faaster.aas_metamodel.models.data_type_def_xsd import DataTypeDefXsd
from faaster.aas_metamodel.models.model_type import ModelType
from faaster.aas_metamodel.models.reference import Reference
from faaster.aas_metamodel.models.submodel_element import SubmodelElement


class SubmodelElementList(SubmodelElement):
    """A submodel element list is an ordered list of submodel elements.

    The numbering starts with zero.

    :param order_relevant: Defines whether order in list is relevant.
    If order_relevant = False then the list is representing a set or a bag.
    :param semantic_id_list_element: Semantic ID
    :param type_value_list_element: The submodel element type of the submodel
    elements contained in the list.
    :param value_type_list_element: The value type of the submodel element contained in the list.
    :param value: Submodel element contained in the list.
    """

    type_model: Literal[ModelType.SUBMODEL_ELEMENT_LIST] = Field(
        alias="modelType", default=ModelType.SUBMODEL_ELEMENT_LIST
    )
    order_relevant: Optional[bool] = True
    semantic_id_list_element: Optional[Reference] = None
    type_value_list_element: AasSubmodelElements
    value_type_list_element: Optional[DataTypeDefXsd] = None
    value: Optional[List[dict]] = []  # needs to be ordered

    def __init__(self, **attrs):
        """Initialize a SubmodelElementList, processing nested values when provided.

        :param self: Instance of SubmodelElementList.
        :param attrs: Attributes dictionary, may include 'value' as a list of elements.
        :return: None
        """
        submodel_element_union, type_model = SubmodelElementProcessor.process_elements(attrs)
        if type_model == "SubmodelElementList":
            if "value" in attrs and isinstance(attrs["value"], list):
                processed_values = []
                for elem in attrs["value"]:
                    type_model = elem.get("modelType", None) or elem.get("type_model", None)
                    instance = getattr(submodel_element_union, type_model)(**elem)
                    processed_values.append(instance.model_dump(by_alias=True))
                attrs["value"] = processed_values
        super().__init__(**attrs)

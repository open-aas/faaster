"""Module defining the Qualifier class with type-value-pair semantics."""

# pylint: disable=duplicate-code

from typing import Optional
from pydantic import Field, model_validator
from faaster.aas_metamodel.models.data_type_def_xsd import DataTypeDefXsd
from faaster.aas_metamodel.models.has_semantics import HasSemantics
from faaster.aas_metamodel.models.qualifier_kind import QualifierKind
from faaster.aas_metamodel.models.qualifier_type import QualifierType
from faaster.aas_metamodel.models.reference import Reference
from faaster.aas_metamodel.models.value_data_type import ValueDataType
from faaster.aas_metamodel.validators import validate_value_type


class Qualifier(HasSemantics):
    """A qualifier is a type-value-pair that makes additional statements.

    :param kind: The qualifier kind describes the kind of the qualifier that is applied
    to the element. Default: ConceptQualifier
    :param type: The qualifier type describes the type of the qualifier that is applied
    to the element.
    :param value_type: Data type of the qualifier value.
    :param value: The qualifier value is the value of the qualifier.
    :param value_id: Reference to the global unique ID of a coded value.
    """

    kind: Optional[QualifierKind] = Field(QualifierKind.CONCEPT_QUALIFIER)
    type: QualifierType
    value_type: DataTypeDefXsd
    value: Optional[ValueDataType] = None
    value_id: Optional[Reference] = None

    @model_validator(mode="before")
    @classmethod
    def check_value_type(cls, values):
        """Validate that the provided value matches the declared valueType before model creation.

        :param cls: The model class where the validator is applied.
        :param values: Dictionary of incoming field values.
        :return: The (possibly modified) dictionary of field values.
        """
        if "valueType" in values:
            modified_value = values.get("value")
            value_type_str = values.get("valueType")

            if modified_value is not None:
                validate_value_type(modified_value, value_type_str)

        return values

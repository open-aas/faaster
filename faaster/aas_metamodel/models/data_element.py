"""A data element is a submodel element that is not further composed out of other elements."""

from faaster.aas_metamodel.models.submodel_element import SubmodelElement


class DataElement(SubmodelElement):
    """A data element is a submodel element that is not further composed out of other elements.

    A data element is a submodel element that has a value. The type of value differs for
    different subtypes of data elements.

    Constraint AASd-090: For data elements category (inherited by Referable) shall be
    one of the following values: CONSTANT, PARAMETER or VARIABLE. Default: VARIABLE.
    """

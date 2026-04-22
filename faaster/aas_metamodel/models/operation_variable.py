"""Submodel element that is used as input and/or output variable of an operation."""

from faaster.aas_metamodel.dto import DTO


class OperationVariable(DTO):
    """Submodel element that is used as input and/or output variable of an operation.

    :param value: Describes an argument or result of an operation via a submodel element.
    """

    value: dict  # Child from Submodel Element (Property, Entity, File, Blob...)

    def __init__(self, **attrs):
        """Initialize the object by resolving and instantiating the correct SubmodelElement type.

        :param self: Instance of the class.
        :param attrs: Attributes containing a 'value' dict with the modelType/type_model key.
        :return: None
        """
        path = 'faaster.aas_metamodel.models.submodel_element_union'
        core = __import__(path)

        aas_metamodel = getattr(core, 'aas_metamodel')
        models = getattr(aas_metamodel, 'models')
        submodel_element_union = getattr(models, 'submodel_element_union')
        model_type = attrs['value'].get('modelType', None) or attrs['value'].get('type_model', None)
        instance = getattr(submodel_element_union, model_type)(**attrs['value'])
        attrs = dict()
        attrs['value'] = instance.model_dump(by_alias=True)
        super().__init__(**attrs)

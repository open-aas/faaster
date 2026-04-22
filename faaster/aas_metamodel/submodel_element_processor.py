class SubmodelElementProcessor:
    """Processor for submodel elements, providing utility methods to handle attributes."""

    @staticmethod
    def process_elements(attrs):
        """Processes element attributes and retrieves the associated DTO module and the model type.

        :param attrs: An object or dict containing submodel element attributes.
        If it has a `dict`-like interface, it will be converted to a dictionary.
        :return: A tuple containing:
        1. The `submodel_element_union` class/module from the DTO.
        2. The model type as a string.
        """
        path = "faaster.aas_metamodel.models.submodel_element_union"
        mod = __import__(path)

        aas_metamodel = getattr(mod, "aas_metamodel")
        models = getattr(aas_metamodel, "models")
        submodel_element_union = getattr(models, "submodel_element_union")

        if hasattr(attrs, "dict"):
            attrs = attrs.model_dump()

        type_model = attrs.get("modelType", None) or attrs.get("type_model", None)
        return submodel_element_union, type_model

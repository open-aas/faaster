from faaster.interfaces import IAddressSpace, IElementCreator, INode
from .creators.aas_creator import AASCreator
from .creators.submodel_creator import SubmodelCreator
from .creators.property_creator import PropertyCreator
from .creators.operation_creator import OperationCreator
from .creators.collection_creator import CollectionCreator
from .creators.range_creator import RangeCreator
from .creators.multi_language_property_creator import MultiLanguagePropertyCreator
from .creators.reference_element_creator import ReferenceElementCreator
from .creators.file_creator import FileCreator
from .creators.basic_event_element_creator import BasicEventElementCreator
from .creators.concept_description_creator import ConceptDescriptionCreator
from .creators.base import BaseCreator


class AASElementCreator(IElementCreator):

    def __init__(
        self,
        aas: BaseCreator,
        submodel: BaseCreator,
        prop: BaseCreator,
        operation: BaseCreator,
        collection: BaseCreator,
        rg: BaseCreator,
        mlp: BaseCreator,
        reference_element: BaseCreator,
        file: BaseCreator,
        event: BaseCreator,
        concept_description: BaseCreator,
    ) -> None:
        self._aas = aas
        self._submodel = submodel
        self._property = prop
        self._operation = operation
        self._collection = collection
        self._range = rg
        self._mlp = mlp
        self._reference_element = reference_element
        self._file = file
        self._event = event
        self._concept_description = concept_description

    async def create_aas(self, parent, element, address_space):
        return await self._aas.create(parent, element, address_space)

    async def create_submodel(self, parent, element, address_space):
        return await self._submodel.create(parent, element, address_space)

    async def create_property(self, parent, element, address_space):
        return await self._property.create(parent, element, address_space)

    async def create_operation(self, parent, element, address_space):
        return await self._operation.create(parent, element, address_space)

    async def create_submodel_element_collection(self, parent, element, address_space):
        return await self._collection.create(parent, element, address_space)

    async def create_range(self, parent, element, address_space):
        return await self._range.create(parent, element, address_space)

    async def create_multi_language_property(self, parent, element, address_space):
        return await self._mlp.create(parent, element, address_space)

    async def create_reference_element(self, parent, element, address_space):
        return await self._reference_element.create(parent, element, address_space)

    async def create_file(self, parent, element, address_space):
        return await self._file.create(parent, element, address_space)

    async def create_basic_event_element(self, parent, element, address_space):
        return await self._event.create(parent, element, address_space)

    async def create_concept_description(self, parent, element, address_space):
        return await self._concept_description.create(parent, element, address_space)

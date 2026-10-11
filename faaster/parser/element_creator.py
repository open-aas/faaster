from typing import Optional
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
from .creators.submodel_element_list_creator import SubmodelElementListCreator
from .creators.entity_creator import EntityCreator
from .creators.relationship_element_creator import RelationshipElementCreator
from .creators.capability_creator import CapabilityCreator
from .creators.blob_creator import BlobCreator
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
        submodel_element_list: Optional[BaseCreator] = None,
        entity: Optional[BaseCreator] = None,
        relationship_element: Optional[BaseCreator] = None,
        capability: Optional[BaseCreator] = None,
        blob: Optional[BaseCreator] = None,
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
        self._list = submodel_element_list or SubmodelElementListCreator()
        self._entity = entity or EntityCreator()
        self._relationship = relationship_element or RelationshipElementCreator()
        self._capability = capability or CapabilityCreator()
        self._blob = blob or BlobCreator()

    async def create_aas(self, parent, element, address_space):
        return await self._aas.create(parent, element, address_space)

    async def create_submodel(self, parent, element, address_space):
        return await self._submodel.create(parent, element, address_space)

    async def create_property(self, parent, element, address_space, name=None):
        return await self._property.create(parent, element, address_space, name=name)

    async def create_operation(self, parent, element, address_space, name=None):
        return await self._operation.create(parent, element, address_space, name=name)

    async def create_submodel_element_collection(self, parent, element, address_space, name=None):
        return await self._collection.create(parent, element, address_space, name=name)

    async def create_range(self, parent, element, address_space, name=None):
        return await self._range.create(parent, element, address_space, name=name)

    async def create_multi_language_property(self, parent, element, address_space, name=None):
        return await self._mlp.create(parent, element, address_space, name=name)

    async def create_reference_element(self, parent, element, address_space, name=None):
        return await self._reference_element.create(parent, element, address_space, name=name)

    async def create_file(self, parent, element, address_space, name=None):
        return await self._file.create(parent, element, address_space, name=name)

    async def create_basic_event_element(self, parent, element, address_space, name=None):
        return await self._event.create(parent, element, address_space, name=name)

    async def create_concept_description(self, parent, element, address_space):
        return await self._concept_description.create(parent, element, address_space)

    async def create_submodel_element_list(self, parent, element, address_space, name=None):
        return await self._list.create(parent, element, address_space, name=name)

    async def create_entity(self, parent, element, address_space, name=None):
        return await self._entity.create(parent, element, address_space, name=name)

    async def create_relationship_element(self, parent, element, address_space, name=None):
        return await self._relationship.create(parent, element, address_space, name=name)

    async def create_capability(self, parent, element, address_space, name=None):
        return await self._capability.create(parent, element, address_space, name=name)

    async def create_blob(self, parent, element, address_space, name=None):
        return await self._blob.create(parent, element, address_space, name=name)

    async def refresh_metadata(self, node, element, address_space):
        # contêineres: os metadados são recriados sem tocar nos filhos
        creators = {
            "Submodel": self._submodel,
            "SubmodelElementCollection": self._collection,
            "SubmodelElementList": self._list,
            "Entity": self._entity,
            "AnnotatedRelationshipElement": self._relationship,
            "Property": self._property,
        }
        creator = creators.get(element.type_model)
        if creator is None:
            raise NotImplementedError(f"Metadata refresh is not supported for {element.type_model}")
        await creator.add_metadata(node, element, address_space)

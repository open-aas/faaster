"""Union type definition for all Submodel Element DTOs."""

from typing import Annotated, Union
from pydantic import Field
from faaster.aas_metamodel.models.annotated_relationship_element import AnnotatedRelationshipElement
from faaster.aas_metamodel.models.basic_event_element import BasicEventElement
from faaster.aas_metamodel.models.blob import Blob
from faaster.aas_metamodel.models.capability import Capability
from faaster.aas_metamodel.models.entity import Entity
from faaster.aas_metamodel.models.file import File
from faaster.aas_metamodel.models.multi_language_property import MultiLanguageProperty
from faaster.aas_metamodel.models.operation import Operation
from faaster.aas_metamodel.models.property import Property
from faaster.aas_metamodel.models.range import Range
from faaster.aas_metamodel.models.reference_element import ReferenceElement
from faaster.aas_metamodel.models.relationship_element import RelationshipElement
from faaster.aas_metamodel.models.submodel_element_collection import SubmodelElementCollection
from faaster.aas_metamodel.models.submodel_element_list import SubmodelElementList

#: Union type covering all Submodel Element DTOs with type_model as discriminator.
SubmodelElementUnion = Annotated[
    Union[
        AnnotatedRelationshipElement,
        BasicEventElement,
        Blob,
        Capability,
        Entity,
        File,
        MultiLanguageProperty,
        Operation,
        Property,
        Range,
        ReferenceElement,
        RelationshipElement,
        SubmodelElementCollection,
        SubmodelElementList,
    ],
    Field(discriminator="type_model"),
]

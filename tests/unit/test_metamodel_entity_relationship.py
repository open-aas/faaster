"""
Entity e AnnotatedRelationshipElement conforme o schema JSON da Part 1
(V3.x): annotations, specificAssetIds e entityType opcional.
"""
import pytest
from pydantic import ValidationError

from faaster.aas_metamodel.exceptions import InvalidFieldException
from faaster.aas_metamodel.models.annotated_relationship_element import AnnotatedRelationshipElement
from faaster.aas_metamodel.models.entity import Entity


REF = {"type": "ModelReference", "keys": [{"type": "Submodel", "value": "urn:sm"}]}
PROP = {"modelType": "Property", "idShort": "Torque", "valueType": "xs:double", "value": "3.0"}


def relationship(**extra):
    return AnnotatedRelationshipElement(
        modelType="AnnotatedRelationshipElement", idShort="Mounted", first=REF, second=REF, **extra
    )


def entity(**extra):
    return Entity(modelType="Entity", idShort="Motor", **extra)


def test_annotations_are_read():
    element = relationship(annotations=[PROP])

    assert [a["idShort"] for a in element.annotations] == ["Torque"]
    assert element.model_dump(by_alias=True)["annotations"][0]["idShort"] == "Torque"


def test_legacy_singular_annotation_is_accepted():
    assert [a["idShort"] for a in relationship(annotation=[PROP]).annotations] == ["Torque"]


def test_annotations_require_id_short():
    with pytest.raises((InvalidFieldException, ValidationError)):
        relationship(annotations=[{k: v for k, v in PROP.items() if k != "idShort"}])


def test_specific_asset_ids_are_read():
    element = entity(
        entityType="SelfManagedEntity",
        specificAssetIds=[{"name": "serialNumber", "value": "M-1"}, {"name": "batch", "value": "B-7"}],
    )

    assert [(s.name, s.value) for s in element.specific_asset_ids] == [("serialNumber", "M-1"), ("batch", "B-7")]
    assert element.model_dump(by_alias=True)["specificAssetIds"][1]["name"] == "batch"


def test_legacy_singular_specific_asset_id_is_accepted():
    element = entity(entityType="SelfManagedEntity", specificAssetId={"name": "serialNumber", "value": "M-1"})
    assert [s.name for s in element.specific_asset_ids] == ["serialNumber"]


def test_entity_type_is_optional():
    assert entity(statements=[PROP]).entity_type is None


def test_self_managed_entity_needs_an_asset_id():
    with pytest.raises((InvalidFieldException, ValidationError)):
        entity(entityType="SelfManagedEntity")


def test_self_managed_entity_with_specific_asset_ids_only():
    element = entity(entityType="SelfManagedEntity", specificAssetIds=[{"name": "serialNumber", "value": "M-1"}])
    assert element.global_asset_id is None


def test_co_managed_entity_has_no_asset_ids():
    with pytest.raises((InvalidFieldException, ValidationError)):
        entity(entityType="CoManagedEntity", specificAssetIds=[{"name": "serialNumber", "value": "M-1"}])

"""SubmodelElementList, Entity, (Annotated)RelationshipElement, Blob and Capability in OPC UA.

Before, the parser skipped these types (and everything nested in them) with a warning: in the
IDTA template corpus (FTM experiment E3) only 51% of the elements reached the address space.
"""
import json
from argparse import Namespace

import pytest

from faaster.asset_administration_shell import AssetAdministrationShell

REF = {"type": "ModelReference", "keys": [{"type": "Submodel", "value": "urn:sm:other"}]}


def prop(id_short=None, value="1", **extra):
    element = {"modelType": "Property", "valueType": "xs:int", "value": value, **extra}
    return element | ({"idShort": id_short} if id_short else {})


MODEL = {
    "assetAdministrationShells": [{
        "modelType": "AssetAdministrationShell", "id": "urn:aas:1", "idShort": "Shell",
        "assetInformation": {"assetKind": "Instance", "globalAssetId": "urn:asset:1"},
        "submodels": [{"type": "ModelReference",
                       "keys": [{"type": "Submodel", "value": "urn:sm:1"}]}],
    }],
    "submodels": [{
        "modelType": "Submodel", "id": "urn:sm:1", "idShort": "Structure",
        "submodelElements": [
            {"modelType": "SubmodelElementList", "idShort": "Readings",
             "typeValueListElement": "Property", "valueTypeListElement": "xs:int",
             "value": [prop(value="10"), prop(value="20", qualifiers=[
                 {"type": "faaster:dynamic", "valueType": "xs:boolean", "value": "true"}])]},
            {"modelType": "SubmodelElementList", "idShort": "Markings",
             "typeValueListElement": "SubmodelElementCollection",
             "value": [{"modelType": "SubmodelElementCollection",
                        "value": [prop("MarkingName", "7")]}]},
            {"modelType": "Entity", "idShort": "Motor", "entityType": "SelfManagedEntity",
             "specificAssetIds": [{"name": "SerialNumber", "value": "SN-1"}],
             "statements": [prop("Speed", "1500")]},
            {"modelType": "RelationshipElement", "idShort": "PartOf", "first": REF, "second": REF},
            {"modelType": "AnnotatedRelationshipElement", "idShort": "Wired", "first": REF,
             "second": REF, "annotations": [prop("Cable", "3")]},
            {"modelType": "Blob", "idShort": "Logo", "contentType": "image/png",
             "value": "iVBORw0KGgo="},
            {"modelType": "Capability", "idShort": "Drilling"},
        ],
    }],
}  # fmt: skip


@pytest.fixture
async def parsed(tmp_path):
    model = tmp_path / "model.json"
    model.write_text(json.dumps(MODEL))
    aas = AssetAdministrationShell(Namespace(url_database=None))
    server = aas._opcua_server
    await server.init()
    ns = await server.register_namespace("urn:faaster:server")
    aas.address_space.set_namespace("urn:faaster:server")
    historized = await aas.parser.parse(str(model))
    submodel = aas.parser._node_registry.node_submodels["Structure"]._node
    yield submodel, ns, historized, aas.parser._node_registry


async def _value(node, ns, *path):
    target = await node.get_child([f"{ns}:{p}" for p in path])
    return await target.read_value()


async def test_list_items_are_named_by_position(parsed):
    submodel, ns, _, _ = parsed
    assert await _value(submodel, ns, "Readings", "[0]", "Value") == 10
    assert await _value(submodel, ns, "Readings", "[1]", "Value") == 20
    assert await _value(submodel, ns, "Readings", "TypeValueListElement") == "Property"


async def test_collections_inside_a_list(parsed):
    """A list item collection was rebuilt from its dump, re-validating the ``[i]`` name."""
    submodel, ns, _, _ = parsed
    assert await _value(submodel, ns, "Markings", "[0]", "MarkingName", "Value") == 7


async def test_dynamic_property_inside_a_list_is_registered(parsed):
    _, _, historized, registry = parsed
    assert registry.get_by_path("Structure/Readings/[1]/Value") is not None
    assert len(historized) == 1


async def test_entity_with_statements_and_specific_asset_ids(parsed):
    submodel, ns, _, _ = parsed
    assert await _value(submodel, ns, "Motor", "Speed", "Value") == 1500
    assert await _value(submodel, ns, "Motor", "EntityType") == "SelfManagedEntity"
    assert await _value(submodel, ns, "Motor", "SpecificAssetIds", "SerialNumber") == "SN-1"


async def test_relationships_blob_and_capability(parsed):
    submodel, ns, _, _ = parsed
    assert await _value(submodel, ns, "PartOf", "First", "Key[0]@Submodel") == "urn:sm:other"
    assert await _value(submodel, ns, "Wired", "Annotations", "Cable", "Value") == 3
    assert await _value(submodel, ns, "Logo", "ContentType") == "image/png"
    assert await _value(submodel, ns, "Drilling", "ModelType") == "Capability"

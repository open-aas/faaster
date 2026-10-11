"""
Parser → address space OPC UA para SubmodelElementList, Entity,
RelationshipElement, AnnotatedRelationshipElement, Capability e Blob.
"""
import copy
from argparse import Namespace

import pytest
from asyncua import ua

from faaster.asset_administration_shell import AssetAdministrationShell

from .structures_model import MODEL, SUBMODEL_ID, write_model


@pytest.fixture
async def aas(tmp_path):
    aas = AssetAdministrationShell(Namespace(url_database=None))
    server = aas._opcua_server
    await server.init()
    await server.register_namespace("urn:faaster:server")
    aas.address_space.set_namespace("urn:faaster:server")
    aas.historized = await aas.parser.parse(str(write_model(tmp_path)))
    try:
        yield aas
    finally:
        await server.iserver.stop()


def element(aas, path):
    node = aas.node_registry.get_element_node(SUBMODEL_ID, path)
    assert node is not None, f"no node for {path}"
    return node.raw


async def children(node):
    return {(await child.read_browse_name()).Name: child for child in await node.get_children()}


async def value_of(node, *names):
    for name in names:
        node = (await children(node))[name]
    return await node.read_value()


# -----------------------------------------------------------------------------
# SubmodelElementList
# -----------------------------------------------------------------------------

async def test_list_items_are_named_by_index(aas):
    setpoints = element(aas, "Setpoints")
    nodes = await children(setpoints)

    assert {"[0]", "[1]", "[2]"} <= set(nodes)
    assert [await value_of(setpoints, f"[{i}]", "Value") for i in range(3)] == [10.0, 20.0, 30.0]
    # itens de lista não têm idShort (AASd-120)
    assert "IdShort" not in await children(nodes["[0]"])


async def test_list_metadata(aas):
    setpoints = element(aas, "Setpoints")

    assert await value_of(setpoints, "IdShort") == "Setpoints"
    assert await value_of(setpoints, "OrderRelevant") is True
    assert await value_of(setpoints, "TypeValueListElement") == "Property"
    assert await value_of(setpoints, "ValueTypeListElement") == "xs:double"
    assert await value_of(setpoints, "SemanticIdListElement", "Type") == "ExternalReference"
    assert await value_of(setpoints, "SemanticIdListElement", "Key[0]@GlobalReference") == "urn:faaster:test:setpoint"


async def test_list_items_are_addressed_like_the_api(aas):
    registry = aas.node_registry

    assert await registry.get_value_node(SUBMODEL_ID, "Setpoints[2]").node.get_value() == 30.0
    assert await registry.get_value_node(SUBMODEL_ID, "Layers[1].Thickness").node.get_value() == 2.5
    assert registry.get_element_node(SUBMODEL_ID, "Layers[0]") is not None
    assert [await n.get_value() for n in [
        registry.get_value_node(SUBMODEL_ID, f"Setpoints[{i}]").node for i in range(3)
    ]] == [10.0, 20.0, 30.0]


async def test_children_of_a_list_item(aas):
    layer = element(aas, "Layers[1]")
    assert await value_of(layer, "Thickness", "Value") == 2.5


# -----------------------------------------------------------------------------
# Entity
# -----------------------------------------------------------------------------

async def test_entity_metadata(aas):
    motor = element(aas, "Motor")

    assert await value_of(motor, "ModelType") == "Entity"
    assert await value_of(motor, "EntityType") == "SelfManagedEntity"
    assert await value_of(motor, "GlobalAssetId") == "urn:faaster:test:asset:motor"
    assert await value_of(motor, "SpecificAssetIds", "serialNumber") == "M-001"
    assert await value_of(motor, "Description", "en") == "Drive motor"


async def test_entity_statements(aas):
    motor = element(aas, "Motor")

    assert await value_of(motor, "Power", "Value") == 1.5
    assert await value_of(motor, "Plate", "Rpm", "Value") == 1750
    assert await aas.node_registry.get_value_node(SUBMODEL_ID, "Motor.Plate.Rpm").node.get_value() == 1750


# -----------------------------------------------------------------------------
# Relacionamentos, Capability e Blob
# -----------------------------------------------------------------------------

async def test_relationship_element_references(aas):
    drives = element(aas, "Drives")

    assert await value_of(drives, "ModelType") == "RelationshipElement"
    assert await value_of(drives, "First", "Type") == "ModelReference"
    assert await value_of(drives, "First", "Key[0]@Submodel") == SUBMODEL_ID
    assert await value_of(drives, "First", "Key[1]@Entity") == "Motor"
    assert await value_of(drives, "Second", "Key[1]@SubmodelElementList") == "Layers"


async def test_annotated_relationship_annotations(aas):
    mounted = element(aas, "Mounted")

    assert await value_of(mounted, "Second", "Key[1]@SubmodelElementList") == "Setpoints"
    assert await value_of(mounted, "Torque", "Value") == 3.0
    assert await aas.node_registry.get_value_node(SUBMODEL_ID, "Mounted.Torque").node.get_value() == 3.0


async def test_capability(aas):
    welding = element(aas, "Welding")

    assert await value_of(welding, "ModelType") == "Capability"
    assert await value_of(welding, "SemanticId", "ConceptDescription") == "urn:faaster:test:cd:welding"


async def test_blob_value_is_decoded(aas):
    firmware = element(aas, "Firmware")

    assert await value_of(firmware, "ContentType") == "application/octet-stream"
    value = (await children(firmware))["Value"]
    assert await value.read_value() == b"\x00\x01\x02"
    assert (await value.read_data_type_as_variant_type()) == ua.VariantType.ByteString


# -----------------------------------------------------------------------------
# HDA dentro de listas e entidades
# -----------------------------------------------------------------------------

@pytest.fixture
async def variable_aas(tmp_path):
    model = copy.deepcopy(MODEL)
    elements = model["submodels"][0]["submodelElements"]
    elements[0]["value"][1]["category"] = "VARIABLE"
    elements[2]["statements"][0]["category"] = "VARIABLE"

    aas = AssetAdministrationShell(Namespace(url_database=None))
    server = aas._opcua_server
    await server.init()
    await server.register_namespace("urn:faaster:server")
    aas.address_space.set_namespace("urn:faaster:server")
    historized = await aas.parser.parse(str(write_model(tmp_path, model)))
    try:
        yield aas, historized
    finally:
        await server.iserver.stop()


async def test_variables_inside_lists_and_entities_are_historized(variable_aas):
    aas, historized = variable_aas
    registry = aas.node_registry

    item = registry.get_by_path("Structures/Setpoints/[1]/Value")
    power = registry.get_by_path("Structures/Motor/Power/Value")

    assert {item.node.node_id, power.node.node_id} == {node.node_id for node in historized}
    assert registry.nodes_in_use(SUBMODEL_ID, "Setpoints") == ["Setpoints[1] (historized)"]
    assert registry.nodes_in_use(SUBMODEL_ID, "Motor") == ["Motor.Power (historized)"]

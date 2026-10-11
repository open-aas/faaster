"""
API HTTP/REST sobre listas, entidades e relacionamentos anotados agora
representados no address space: valores vivos e alterações estruturais.
"""
import copy
from argparse import Namespace

import httpx
import pytest

from faaster.api import AASRepository, create_app
from faaster.asset_administration_shell import AssetAdministrationShell

from ..integration.structures_model import MODEL, SUBMODEL_ID, prop, write_model
from .conftest import encode


ELEMENTS = f"/submodels/{encode(SUBMODEL_ID)}/submodel-elements"


async def _start(tmp_path, model):
    aas = AssetAdministrationShell(Namespace(url_database=None, http_port=None))
    server = aas._opcua_server
    await server.init()
    await server.register_namespace("urn:faaster:server")
    aas.address_space.set_namespace("urn:faaster:server")
    await aas.parser.parse(str(write_model(tmp_path, model)))

    app = create_app(
        repository=AASRepository(aas.parser.document),
        registry=aas.node_registry,
        address_space=aas.address_space,
        model_sync=aas.parser,
    )
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://faaster")
    return aas, client


@pytest.fixture
async def api(tmp_path):
    aas, client = await _start(tmp_path, MODEL)
    try:
        yield aas, client
    finally:
        await client.aclose()
        await aas._opcua_server.iserver.stop()


@pytest.fixture
async def historized_api(tmp_path):
    model = copy.deepcopy(MODEL)
    model["submodels"][0]["submodelElements"][0]["value"][2]["category"] = "VARIABLE"
    aas, client = await _start(tmp_path, model)
    try:
        yield aas, client
    finally:
        await client.aclose()
        await aas._opcua_server.iserver.stop()


def value_node(aas, path):
    entry = aas.node_registry.get_value_node(SUBMODEL_ID, path)
    assert entry is not None, f"no value node for {path}"
    return entry.node


async def list_item_names(aas, path="Setpoints"):
    node = aas.node_registry.get_element_node(SUBMODEL_ID, path).raw
    names = [(await child.read_browse_name()).Name for child in await node.get_children()]
    return sorted(name for name in names if name.startswith("["))


# -----------------------------------------------------------------------------
# Valores vivos
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("path, value", [
    ("Setpoints[1]", 21.5),
    ("Layers[0].Thickness", 9.0),
    ("Motor.Power", 2.25),
    ("Motor.Plate.Rpm", 3000),
    ("Mounted.Torque", 4.5),
])
async def test_nested_properties_are_live(api, path, value):
    aas, client = api

    response = await client.patch(f"{ELEMENTS}/{path}/$value", json=value)

    assert response.status_code == 204
    assert await value_node(aas, path).get_value() == value
    assert (await client.get(f"{ELEMENTS}/{path}/$value")).json() == value


async def test_entity_value_only_shows_live_statements(api):
    aas, client = api
    await value_node(aas, "Motor.Power").set_value(7.5)

    result = (await client.get(f"{ELEMENTS}/Motor/$value")).json()

    assert result["statements"]["Power"] == 7.5
    assert result["entityType"] == "SelfManagedEntity"


# -----------------------------------------------------------------------------
# Listas: anexar, remover, substituir
# -----------------------------------------------------------------------------

async def test_post_appends_list_item_node(api):
    aas, client = api

    response = await client.post(f"{ELEMENTS}/Setpoints", json=prop(value="40"))

    assert response.status_code == 201
    assert response.headers["location"].endswith("/submodel-elements/Setpoints%5B3%5D")
    assert await value_node(aas, "Setpoints[3]").get_value() == 40.0
    assert await list_item_names(aas) == ["[0]", "[1]", "[2]", "[3]"]


async def test_delete_from_the_middle_reindexes_items_and_keeps_live_values(api):
    aas, client = api
    await value_node(aas, "Setpoints[2]").set_value(33.0)

    response = await client.delete(f"{ELEMENTS}/Setpoints[0]")

    assert response.status_code == 204
    assert await list_item_names(aas) == ["[0]", "[1]"]
    assert await value_node(aas, "Setpoints[0]").get_value() == 20.0
    assert await value_node(aas, "Setpoints[1]").get_value() == 33.0
    assert aas.node_registry.get_value_node(SUBMODEL_ID, "Setpoints[2]") is None
    assert (await client.get(f"{ELEMENTS}/Setpoints/$value")).json() == [20.0, 33.0]


async def test_delete_list_item_with_children_reindexes_subtree(api):
    aas, client = api
    await value_node(aas, "Layers[1].Thickness").set_value(8.0)

    assert (await client.delete(f"{ELEMENTS}/Layers[0]")).status_code == 204

    assert await value_node(aas, "Layers[0].Thickness").get_value() == 8.0
    assert aas.node_registry.get_element_node(SUBMODEL_ID, "Layers[1]") is None


async def test_delete_last_item_keeps_the_others(api):
    aas, client = api
    before = value_node(aas, "Setpoints[0]").node_id

    assert (await client.delete(f"{ELEMENTS}/Setpoints[2]")).status_code == 204

    assert await list_item_names(aas) == ["[0]", "[1]"]
    assert value_node(aas, "Setpoints[0]").node_id == before


async def test_delete_is_refused_when_a_shifted_item_is_historized(historized_api):
    aas, client = historized_api

    response = await client.delete(f"{ELEMENTS}/Setpoints[0]")

    assert response.status_code == 409
    assert "Setpoints[2] (historized)" in response.json()["messages"][0]["text"]
    assert await list_item_names(aas) == ["[0]", "[1]", "[2]"]


async def test_put_list_with_fewer_items(api):
    aas, client = api
    body = (await client.get(f"{ELEMENTS}/Setpoints")).json()
    first = value_node(aas, "Setpoints[0]").node_id
    body["value"] = body["value"][:2]

    assert (await client.put(f"{ELEMENTS}/Setpoints", json=body)).status_code == 204

    assert await list_item_names(aas) == ["[0]", "[1]"]
    # item inalterado: mesmo nó
    assert value_node(aas, "Setpoints[0]").node_id == first


async def test_put_list_with_more_items(api):
    aas, client = api
    body = (await client.get(f"{ELEMENTS}/Setpoints")).json()
    body["value"].append(prop(value="99"))

    assert (await client.put(f"{ELEMENTS}/Setpoints", json=body)).status_code == 204

    assert await value_node(aas, "Setpoints[3]").get_value() == 99.0


# -----------------------------------------------------------------------------
# Entity e AnnotatedRelationshipElement: alterações no lugar
# -----------------------------------------------------------------------------

async def test_entity_patch_keeps_statement_nodes(api):
    aas, client = api
    power = value_node(aas, "Motor.Power")
    await power.set_value(5.0)

    # PATCH (level=core): os statements vêm do modelo guardado
    response = await client.patch(
        f"{ELEMENTS}/Motor",
        json={"modelType": "Entity", "idShort": "Motor", "entityType": "SelfManagedEntity",
              "globalAssetId": "urn:faaster:test:asset:motor-2"},
    )

    assert response.status_code == 204
    assert value_node(aas, "Motor.Power") is power
    assert await power.get_value() == 5.0
    motor = aas.node_registry.get_element_node(SUBMODEL_ID, "Motor").raw
    names = {(await c.read_browse_name()).Name: c for c in await motor.get_children()}
    assert await names["GlobalAssetId"].read_value() == "urn:faaster:test:asset:motor-2"


async def test_entity_metadata_patch_keeps_statement_nodes(api):
    aas, client = api
    power = value_node(aas, "Motor.Power")

    response = await client.patch(
        f"{ELEMENTS}/Motor/$metadata",
        json={"modelType": "Entity", "idShort": "Motor",
              "description": [{"language": "pt", "text": "Motor de acionamento"}]},
    )

    assert response.status_code == 204
    assert value_node(aas, "Motor.Power") is power
    motor = aas.node_registry.get_element_node(SUBMODEL_ID, "Motor").raw
    names = {(await c.read_browse_name()).Name: c for c in await motor.get_children()}
    description = {(await c.read_browse_name()).Name: await c.read_value() for c in await names["Description"].get_children()}
    assert description == {"pt": "Motor de acionamento"}


async def test_post_statement_into_entity(api):
    aas, client = api

    response = await client.post(f"{ELEMENTS}/Motor", json=prop("Voltage", "400"))

    assert response.status_code == 201
    assert await value_node(aas, "Motor.Voltage").get_value() == 400.0


async def test_delete_annotation(api):
    aas, client = api

    assert (await client.delete(f"{ELEMENTS}/Mounted.Torque")).status_code == 204
    assert aas.node_registry.get_value_node(SUBMODEL_ID, "Mounted.Torque") is None


async def test_relationship_rebuild_on_reference_change(api):
    aas, client = api
    body = (await client.get(f"{ELEMENTS}/Drives")).json()
    body["second"]["keys"][1] = {"type": "Capability", "value": "Welding"}

    assert (await client.put(f"{ELEMENTS}/Drives", json=body)).status_code == 204

    drives = aas.node_registry.get_element_node(SUBMODEL_ID, "Drives").raw
    second = [c for c in await drives.get_children() if (await c.read_browse_name()).Name == "Second"][0]
    keys = {(await c.read_browse_name()).Name: await c.read_value() for c in await second.get_children()}
    assert keys["Key[1]@Capability"] == "Welding"

"""
Submodel Repository Service — leitura (SSP-002), com valores vivos do OPC UA.
"""
import json

from faaster.api.encoding import b64url_encode
from faaster.api.profiles import SUBMODEL_REPOSITORY_READ
from faaster.parser.creators.base import resolve_variant_type

from .conftest import NAMEPLATE_ID, OPERATIONAL_ID, SHOWCASE_ID, encode


def _assert_result_error(response, status: int) -> None:
    assert response.status_code == status
    message = response.json()["messages"][0]
    assert message["code"] == str(status)
    assert message["messageType"] == "Error"
    assert message["timestamp"].endswith("Z")


# -----------------------------------------------------------------------------
# /description
# -----------------------------------------------------------------------------

async def test_description_lists_profiles(client):
    response = await client.get("/description")
    assert response.status_code == 200
    assert SUBMODEL_REPOSITORY_READ in response.json()["profiles"]


# -----------------------------------------------------------------------------
# GetAllSubmodels
# -----------------------------------------------------------------------------

async def test_get_all_submodels(client):
    response = await client.get("/submodels")
    assert response.status_code == 200
    body = response.json()
    assert [s["id"] for s in body["result"]] == [OPERATIONAL_ID, NAMEPLATE_ID, SHOWCASE_ID]
    assert body["paging_metadata"] == {}


async def test_get_all_submodels_pagination(client):
    first = (await client.get("/submodels", params={"limit": 1})).json()
    assert [s["id"] for s in first["result"]] == [OPERATIONAL_ID]
    cursor = first["paging_metadata"]["cursor"]

    second = (await client.get("/submodels", params={"limit": 2, "cursor": cursor})).json()
    assert [s["id"] for s in second["result"]] == [NAMEPLATE_ID, SHOWCASE_ID]
    assert "cursor" not in second["paging_metadata"]


async def test_get_all_submodels_filter_by_id_short(client):
    body = (await client.get("/submodels", params={"idShort": "Nameplate"})).json()
    assert [s["id"] for s in body["result"]] == [NAMEPLATE_ID]


async def test_get_all_submodels_filter_by_semantic_id_reference(client):
    reference = {
        "type": "ExternalReference",
        "keys": [{"type": "GlobalReference", "value": "https://admin-shell.io/zvei/nameplate/2/0/Nameplate"}],
    }
    encoded = b64url_encode(json.dumps(reference))
    body = (await client.get("/submodels", params={"semanticId": encoded})).json()
    assert [s["id"] for s in body["result"]] == [NAMEPLATE_ID]


async def test_get_all_submodels_rejects_empty_cursor(client):
    _assert_result_error(await client.get("/submodels", params={"cursor": ""}), 400)


async def test_get_all_submodels_rejects_invalid_cursor(client):
    _assert_result_error(await client.get("/submodels", params={"cursor": "%%%"}), 400)


async def test_get_all_submodels_rejects_invalid_level(client):
    _assert_result_error(await client.get("/submodels", params={"level": "shallow"}), 400)


async def test_get_all_submodels_rejects_zero_limit(client):
    _assert_result_error(await client.get("/submodels", params={"limit": 0}), 400)


# -----------------------------------------------------------------------------
# GetSubmodelById
# -----------------------------------------------------------------------------

async def test_get_submodel_by_id_preserves_model(client):
    body = (await client.get(f"/submodels/{encode(NAMEPLATE_ID)}")).json()
    assert body == {
        "modelType": "Submodel",
        "id": NAMEPLATE_ID,
        "idShort": "Nameplate",
        "semanticId": {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": "https://admin-shell.io/zvei/nameplate/2/0/Nameplate"}],
        },
        "submodelElements": [
            {"modelType": "Property", "idShort": "ManufacturerName", "valueType": "xs:string", "value": "Faaster"}
        ],
    }


async def test_get_submodel_by_id_accepts_padding(client):
    padded = encode(NAMEPLATE_ID) + "=" * (-len(encode(NAMEPLATE_ID)) % 4)
    assert (await client.get(f"/submodels/{padded}")).status_code == 200


async def test_get_submodel_by_id_not_found(client):
    _assert_result_error(await client.get(f"/submodels/{encode('urn:unknown')}"), 404)


async def test_get_submodel_by_id_invalid_encoding(client):
    _assert_result_error(await client.get("/submodels/!!!"), 400)


async def test_get_submodel_level_core_omits_grandchildren(client):
    body = (await client.get(f"/submodels/{encode(OPERATIONAL_ID)}", params={"level": "core"})).json()
    motor = next(e for e in body["submodelElements"] if e["idShort"] == "Motor")
    assert "value" not in motor


async def test_get_submodel_level_deep_keeps_hierarchy(client):
    body = (await client.get(f"/submodels/{encode(OPERATIONAL_ID)}")).json()
    motor = next(e for e in body["submodelElements"] if e["idShort"] == "Motor")
    status = next(e for e in motor["value"] if e["idShort"] == "Status")
    assert status["value"][0]["idShort"] == "Running"


async def test_extent_controls_blob_value(client):
    url = f"/submodels/{encode(OPERATIONAL_ID)}/submodel-elements/Firmware"

    without = (await client.get(url)).json()
    assert "value" not in without
    assert without["contentType"] == "application/octet-stream"

    with_blob = (await client.get(url, params={"extent": "withBlobValue"})).json()
    assert with_blob["value"] == "AAECAw=="


# -----------------------------------------------------------------------------
# GetAllSubmodelElements / GetSubmodelElementByPath
# -----------------------------------------------------------------------------

async def test_get_all_submodel_elements(client):
    body = (await client.get(f"/submodels/{encode(OPERATIONAL_ID)}/submodel-elements")).json()
    assert [e["idShort"] for e in body["result"]] == ["Temperature", "Motor", "Setpoints", "Firmware"]


async def test_get_all_submodel_elements_pagination(client):
    url = f"/submodels/{encode(OPERATIONAL_ID)}/submodel-elements"
    first = (await client.get(url, params={"limit": 3})).json()
    second = (await client.get(url, params={"cursor": first["paging_metadata"]["cursor"]})).json()
    assert [e["idShort"] for e in second["result"]] == ["Firmware"]


async def test_get_submodel_element_nested_path(client):
    url = f"/submodels/{encode(OPERATIONAL_ID)}/submodel-elements/Motor.Status.Running"
    body = (await client.get(url)).json()
    assert body["idShort"] == "Running"
    assert body["value"] == "false"


async def test_get_submodel_element_list_index(client):
    # "[" e "]" vão URL-encoded, como pede a spec
    url = f"/submodels/{encode(OPERATIONAL_ID)}/submodel-elements/Setpoints%5B1%5D"
    body = (await client.get(url)).json()
    assert body["value"] == "20.0"


async def test_get_submodel_element_core_on_collection(client):
    url = f"/submodels/{encode(OPERATIONAL_ID)}/submodel-elements/Motor"
    body = (await client.get(url, params={"level": "core"})).json()
    # filhos diretos presentes, netos omitidos
    assert [e["idShort"] for e in body["value"]] == ["Speed", "Status"]
    assert "value" not in body["value"][1]


async def test_get_submodel_element_not_found(client):
    url = f"/submodels/{encode(OPERATIONAL_ID)}/submodel-elements/Motor.Nope"
    _assert_result_error(await client.get(url), 404)


async def test_get_submodel_element_index_out_of_range(client):
    url = f"/submodels/{encode(OPERATIONAL_ID)}/submodel-elements/Setpoints%5B9%5D"
    _assert_result_error(await client.get(url), 404)


async def test_get_submodel_element_malformed_path(client):
    url = f"/submodels/{encode(OPERATIONAL_ID)}/submodel-elements/Motor..Speed"
    _assert_result_error(await client.get(url), 400)


# -----------------------------------------------------------------------------
# Valores vivos (AAS Tipo 2): o valor vem do nó OPC UA, não do arquivo
# -----------------------------------------------------------------------------

async def test_live_value_from_opcua_node(client, registry):
    entry = registry.get_value_node(OPERATIONAL_ID, "Motor.Speed")
    await entry.node.set_value(1450, resolve_variant_type(entry.value_type))

    url = f"/submodels/{encode(OPERATIONAL_ID)}/submodel-elements/Motor.Speed"
    assert (await client.get(url)).json()["value"] == "1450"


async def test_live_boolean_uses_xsd_lexical_form(client, registry):
    entry = registry.get_value_node(OPERATIONAL_ID, "Motor.Status.Running")
    await entry.node.set_value(True)

    body = (await client.get(f"/submodels/{encode(OPERATIONAL_ID)}")).json()
    motor = next(e for e in body["submodelElements"] if e["idShort"] == "Motor")
    running = motor["value"][1]["value"][0]
    assert running["value"] == "true"


async def test_live_value_of_variable_property(client, registry):
    entry = registry.get_value_node(OPERATIONAL_ID, "Temperature")
    await entry.node.set_value(36.6)

    url = f"/submodels/{encode(OPERATIONAL_ID)}/submodel-elements/Temperature"
    assert (await client.get(url)).json()["value"] == "36.6"

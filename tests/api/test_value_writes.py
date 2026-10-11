"""
Parte 4 — escrita de valores ValueOnly (PATCH .../$value) direto nos nós OPC UA.
"""
from datetime import datetime

import pytest

from faaster.api.errors import BadRequestError
from faaster.api.writer import parse_value, to_node_value
from faaster.interfaces.types import FaasterVariantType

from .conftest import AAS_ID, NAMEPLATE_ID, OPERATIONAL_ID, SHOWCASE_ID, encode


OPERATIONAL = f"/submodels/{encode(OPERATIONAL_ID)}"
ELEMENTS = f"{OPERATIONAL}/submodel-elements"


async def _node_value(registry, path, submodel_id=OPERATIONAL_ID):
    return await registry.get_value_node(submodel_id, path).node.get_value()


def _error_text(response) -> str:
    return response.json()["messages"][0]["text"]


# -----------------------------------------------------------------------------
# PatchSubmodelElementByPath-ValueOnly
# -----------------------------------------------------------------------------

async def test_patch_property_writes_opcua_node(client, registry):
    response = await client.patch(f"{ELEMENTS}/Temperature/$value", json=36.6)

    assert response.status_code == 204
    assert response.content == b""
    assert await _node_value(registry, "Temperature") == 36.6


async def test_written_value_is_served_back(client):
    await client.patch(f"{ELEMENTS}/Motor.Speed/$value", json=1450)

    assert (await client.get(f"{ELEMENTS}/Motor.Speed")).json()["value"] == "1450"
    assert (await client.get(f"{ELEMENTS}/Motor.Speed/$value")).json() == 1450


async def test_patch_accepts_xsd_lexical_string(client, registry):
    assert (await client.patch(f"{ELEMENTS}/Motor.Speed/$value", json="1200")).status_code == 204
    assert await _node_value(registry, "Motor.Speed") == 1200

    assert (await client.patch(f"{ELEMENTS}/Motor.Status.Running/$value", json="true")).status_code == 204
    assert await _node_value(registry, "Motor.Status.Running") is True


async def test_patch_boolean(client, registry):
    assert (await client.patch(f"{ELEMENTS}/Motor.Status.Running/$value", json=False)).status_code == 204
    assert await _node_value(registry, "Motor.Status.Running") is False


async def test_patch_string(client, registry):
    url = f"/submodels/{encode(NAMEPLATE_ID)}/submodel-elements/ManufacturerName/$value"
    assert (await client.patch(url, json="Open AAS")).status_code == 204
    assert await _node_value(registry, "ManufacturerName", NAMEPLATE_ID) == "Open AAS"


async def test_patch_collection_updates_only_given_children(client, registry):
    before = await _node_value(registry, "Motor.Speed")

    response = await client.patch(f"{ELEMENTS}/Motor/$value", json={"Status": {"Running": True}})

    assert response.status_code == 204
    assert await _node_value(registry, "Motor.Status.Running") is True
    assert await _node_value(registry, "Motor.Speed") == before


async def test_patch_submodel_value_only(client, registry):
    body = {"Temperature": 40.0, "Motor": {"Speed": 900, "Status": {"Running": True}}}

    response = await client.patch(f"{OPERATIONAL}/$value", json=body)

    assert response.status_code == 204
    value = (await client.get(f"{OPERATIONAL}/$value")).json()
    assert value["Temperature"] == 40.0
    assert value["Motor"] == {"Speed": 900, "Status": {"Running": True}}


async def test_patch_via_shell_superpath(client, registry):
    url = (
        f"/shells/{encode(AAS_ID)}/submodels/{encode(OPERATIONAL_ID)}"
        "/submodel-elements/Temperature/$value"
    )
    assert (await client.patch(url, json=12.5)).status_code == 204
    assert await _node_value(registry, "Temperature") == 12.5


async def test_patch_level_core_is_accepted(client):
    url = f"{ELEMENTS}/Temperature/$value?level=core"
    assert (await client.patch(url, json=1.0)).status_code == 204


# -----------------------------------------------------------------------------
# Erros — e nada é escrito
# -----------------------------------------------------------------------------

async def test_patch_level_deep_is_rejected(client, registry):
    before = await _node_value(registry, "Temperature")

    response = await client.patch(f"{ELEMENTS}/Temperature/$value?level=deep", json=1.0)

    assert response.status_code == 400
    assert await _node_value(registry, "Temperature") == before


@pytest.mark.parametrize("path, value", [
    ("Temperature", "hot"),
    ("Temperature", True),
    ("Temperature", None),
    ("Motor.Speed", 1.5),
    ("Motor.Speed", "12a"),
    ("Motor.Speed", 2**31),
    ("Motor.Status.Running", "yes"),
    ("Motor.Status.Running", 1),
])
async def test_patch_invalid_value_is_bad_request(client, path, value):
    response = await client.patch(f"{ELEMENTS}/{path}/$value", json=value)
    assert response.status_code == 400


async def test_patch_value_out_of_opcua_node_range(client, registry):
    # xs:int cabe em 40000, mas o nó OPC UA do Faaster é Int16
    response = await client.patch(f"{ELEMENTS}/Motor.Speed/$value", json=40000)

    assert response.status_code == 400
    assert "Int16" in _error_text(response)


async def test_invalid_child_aborts_whole_request(client, registry):
    before = await _node_value(registry, "Temperature")

    body = {"Temperature": 99.9, "Motor": {"Speed": "fast"}}
    response = await client.patch(f"{OPERATIONAL}/$value", json=body)

    assert response.status_code == 400
    assert await _node_value(registry, "Temperature") == before


async def test_unknown_child_is_bad_request(client):
    response = await client.patch(f"{ELEMENTS}/Motor/$value", json={"Torque": 1})

    assert response.status_code == 400
    assert "Torque" in _error_text(response)


async def test_collection_requires_object(client):
    assert (await client.patch(f"{ELEMENTS}/Motor/$value", json=[1])).status_code == 400


async def test_unknown_element_is_not_found(client):
    assert (await client.patch(f"{ELEMENTS}/Missing/$value", json=1)).status_code == 404


async def test_unknown_submodel_is_not_found(client):
    url = f"/submodels/{encode('urn:missing')}/$value"
    assert (await client.patch(url, json={})).status_code == 404


async def test_superpath_requires_submodel_of_the_shell(client):
    url = (
        f"/shells/{encode('urn:faaster:test:aas:2')}/submodels/{encode(OPERATIONAL_ID)}"
        "/submodel-elements/Temperature/$value"
    )
    assert (await client.patch(url, json=1.0)).status_code == 404


async def test_missing_body_is_bad_request(client):
    response = await client.patch(
        f"{ELEMENTS}/Temperature/$value",
        content=b"",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400


async def test_malformed_json_is_bad_request(client):
    response = await client.patch(
        f"{ELEMENTS}/Temperature/$value",
        content=b"{not json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400


async def test_operation_has_no_value(client):
    url = f"/submodels/{encode(SHOWCASE_ID)}/submodel-elements/Reset/$value"
    assert (await client.patch(url, json={})).status_code == 400


@pytest.mark.parametrize("path, value", [
    ("Title", [{"en": "x"}]),
    ("Pressure", {"min": 1, "max": 2}),
    ("Manual", {"contentType": "application/pdf", "value": "x.pdf"}),
])
async def test_elements_without_live_node_are_not_implemented(client, path, value):
    url = f"/submodels/{encode(SHOWCASE_ID)}/submodel-elements/{path}/$value"
    assert (await client.patch(url, json=value)).status_code == 501


async def test_list_children_without_live_node_are_not_implemented(client):
    # o parser ainda não cria nós OPC UA para SubmodelElementList
    assert (await client.patch(f"{ELEMENTS}/Setpoints/$value", json=[1, 2])).status_code == 501


async def test_list_length_must_match(client):
    assert (await client.patch(f"{ELEMENTS}/Setpoints/$value", json=[1])).status_code == 400


# -----------------------------------------------------------------------------
# Conversão de valores
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("value, value_type, expected", [
    (True, "xs:boolean", True),
    ("0", "xs:boolean", False),
    (5, "xs:int", 5),
    ("-7", "xs:long", -7),
    (3.0, "xs:int", 3),
    (2, "xs:double", 2.0),
    ("1.5e3", "xs:double", 1500.0),
    ("abc", "xs:string", "abc"),
    ("abc", None, "abc"),
    ("2026-10-11T10:00:00Z", "xs:dateTime", "2026-10-11T10:00:00Z"),
])
def test_parse_value(value, value_type, expected):
    assert parse_value(value, value_type, "p") == expected


@pytest.mark.parametrize("value, value_type", [
    (-1, "xs:unsignedInt"),
    (0, "xs:positiveInteger"),
    (128, "xs:byte"),
    (1, "xs:string"),
    ("yesterday", "xs:dateTime"),
    (False, "xs:int"),
])
def test_parse_value_rejects(value, value_type):
    with pytest.raises(BadRequestError):
        parse_value(value, value_type, "p")


def test_to_node_value():
    assert to_node_value(7, FaasterVariantType.Int32, "p") == 7
    assert to_node_value(7, FaasterVariantType.String, "p") == "7"
    assert to_node_value(True, FaasterVariantType.String, "p") == "true"
    assert to_node_value("2026-10-11T10:00:00Z", FaasterVariantType.DateTime, "p") == datetime.fromisoformat(
        "2026-10-11T10:00:00Z"
    )
    with pytest.raises(BadRequestError):
        to_node_value(-1, FaasterVariantType.UInt16, "p")

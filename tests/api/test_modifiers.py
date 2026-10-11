"""
Modificadores de conteúdo: $value, $metadata, $reference, $path
(IDTA-01002-3-2 §SerializationModifiers e Annex — SerializationModifier Examples).
"""
from faaster.parser.creators.base import resolve_variant_type

from .conftest import NAMEPLATE_ID, OPERATIONAL_ID, SHOWCASE_ID, encode


OPERATIONAL = f"/submodels/{encode(OPERATIONAL_ID)}"
SHOWCASE = f"/submodels/{encode(SHOWCASE_ID)}"


async def _get(client, url, **params):
    response = await client.get(url, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def _get_error(client, url, status, **params):
    response = await client.get(url, params=params)
    assert response.status_code == status, response.text
    assert response.json()["messages"][0]["code"] == str(status)


# =============================================================================
# $value
# =============================================================================

async def test_submodel_value_only_deep(client):
    body = await _get(client, f"{OPERATIONAL}/$value")
    assert body == {
        "Temperature": 21.5,
        "Motor": {"Speed": 0, "Status": {"Running": False}},
        "Setpoints": [10.0, 20.0],
        "Firmware": {"contentType": "application/octet-stream"},
    }


async def test_submodel_value_only_core_empties_containers(client):
    # Modifier Constraints: filhos diretos SMC → {} e SML → []
    body = await _get(client, f"{OPERATIONAL}/$value", level="core")
    assert body["Motor"] == {}
    assert body["Setpoints"] == []
    assert body["Temperature"] == 21.5


async def test_value_only_with_blob_value(client):
    body = await _get(client, f"{OPERATIONAL}/submodel-elements/Firmware/$value", extent="withBlobValue")
    assert body == {"contentType": "application/octet-stream", "value": "AAECAw=="}


async def test_element_value_only_is_unnamed(client):
    # a raiz não carrega o idShort do elemento requisitado
    assert await _get(client, f"{OPERATIONAL}/submodel-elements/Motor/$value") == {
        "Speed": 0,
        "Status": {"Running": False},
    }
    assert await _get(client, f"{OPERATIONAL}/submodel-elements/Motor.Status.Running/$value") is False
    assert await _get(client, f"{OPERATIONAL}/submodel-elements/Setpoints%5B0%5D/$value") == 10.0


async def test_value_only_reflects_live_opcua_value(client, registry):
    entry = registry.get_value_node(OPERATIONAL_ID, "Motor.Speed")
    await entry.node.set_value(900, resolve_variant_type(entry.value_type))

    assert await _get(client, f"{OPERATIONAL}/submodel-elements/Motor.Speed/$value") == 900


async def test_value_only_of_each_element_type(client):
    body = await _get(client, f"{SHOWCASE}/$value")
    assert body == {
        "Title": [{"en": "Press"}, {"pt": "Prensa"}],
        "Pressure": {"min": 1.5, "max": 6.0},
        "Manual": {"contentType": "application/pdf", "value": "/aasx/manual.pdf"},
        "Vendor": {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": "https://example.com/vendor"}],
        },
        "Gripper": {
            "statements": {"Force": 120},
            "entityType": "SelfManagedEntity",
            "globalAssetId": "urn:faaster:test:asset:gripper",
        },
        # Operations não têm ValueOnly e são omitidas, inclusive dentro de coleções
        "Tools": {},
    }


async def test_value_only_rejected_for_operation(client):
    await _get_error(client, f"{SHOWCASE}/submodel-elements/Reset/$value", 400)


async def test_all_submodel_elements_value_only(client):
    body = await _get(client, f"{OPERATIONAL}/submodel-elements/$value", limit=2)
    assert body["result"] == {"Temperature": 21.5, "Motor": {"Speed": 0, "Status": {"Running": False}}}
    assert "cursor" in body["paging_metadata"]


async def test_all_submodels_value_only(client):
    body = await _get(client, "/submodels/$value", idShort="Nameplate")
    assert body["result"] == [{"ManufacturerName": "Faaster"}]


# =============================================================================
# $metadata
# =============================================================================

async def test_submodel_metadata_has_no_elements(client):
    body = await _get(client, f"{OPERATIONAL}/$metadata")
    assert body["id"] == OPERATIONAL_ID
    assert "submodelElements" not in body
    assert body["semanticId"]["keys"][0]["value"] == "https://example.com/sm/OperationalData/1/0"


async def test_element_metadata_has_no_value(client):
    body = await _get(client, f"{OPERATIONAL}/submodel-elements/Motor.Speed/$metadata")
    assert body == {"modelType": "Property", "idShort": "Speed", "valueType": "xs:int"}

    collection = await _get(client, f"{OPERATIONAL}/submodel-elements/Motor/$metadata")
    assert "value" not in collection


async def test_metadata_rejects_level(client):
    await _get_error(client, f"{OPERATIONAL}/$metadata", 400, level="core")
    await _get_error(client, f"{OPERATIONAL}/submodel-elements/Motor/$metadata", 400, level="deep")


async def test_metadata_rejects_with_blob_value(client):
    await _get_error(client, f"{OPERATIONAL}/submodel-elements/Firmware/$metadata", 400, extent="withBlobValue")


async def test_all_submodels_metadata(client):
    body = await _get(client, "/submodels/$metadata")
    assert [s["id"] for s in body["result"]] == [OPERATIONAL_ID, NAMEPLATE_ID, SHOWCASE_ID]
    assert all("submodelElements" not in s for s in body["result"])


async def test_all_submodel_elements_metadata(client):
    body = await _get(client, f"{OPERATIONAL}/submodel-elements/$metadata")
    assert [e["idShort"] for e in body["result"]] == ["Temperature", "Motor", "Setpoints", "Firmware"]
    assert all("value" not in e for e in body["result"])


# =============================================================================
# $reference
# =============================================================================

async def test_submodel_reference(client):
    assert await _get(client, f"{OPERATIONAL}/$reference") == {
        "type": "ModelReference",
        "keys": [{"type": "Submodel", "value": OPERATIONAL_ID}],
    }


async def test_nested_element_reference(client):
    body = await _get(client, f"{OPERATIONAL}/submodel-elements/Motor.Status.Running/$reference")
    assert body["keys"] == [
        {"type": "Submodel", "value": OPERATIONAL_ID},
        {"type": "SubmodelElementCollection", "value": "Motor"},
        {"type": "SubmodelElementCollection", "value": "Status"},
        {"type": "Property", "value": "Running"},
    ]


async def test_list_item_reference_uses_index(client):
    body = await _get(client, f"{OPERATIONAL}/submodel-elements/Setpoints%5B1%5D/$reference")
    assert body["keys"][-2:] == [
        {"type": "SubmodelElementList", "value": "Setpoints"},
        {"type": "Property", "value": "1"},
    ]


async def test_reference_rejects_level_deep(client):
    await _get_error(client, f"{OPERATIONAL}/$reference", 400, level="deep")
    assert (await client.get(f"{OPERATIONAL}/$reference", params={"level": "core"})).status_code == 200


async def test_all_submodels_reference(client):
    body = await _get(client, "/submodels/$reference", limit=1)
    assert body["result"] == [{"type": "ModelReference", "keys": [{"type": "Submodel", "value": OPERATIONAL_ID}]}]


async def test_all_submodel_elements_reference(client):
    body = await _get(client, f"{OPERATIONAL}/submodel-elements/$reference")
    assert [r["keys"][-1]["value"] for r in body["result"]] == ["Temperature", "Motor", "Setpoints", "Firmware"]


# =============================================================================
# $path
# =============================================================================

async def test_submodel_path_deep(client):
    assert await _get(client, f"{OPERATIONAL}/$path") == [
        "Temperature",
        "Motor",
        "Motor.Speed",
        "Motor.Status",
        "Motor.Status.Running",
        "Setpoints",
        "Setpoints[0]",
        "Setpoints[1]",
        "Firmware",
    ]


async def test_submodel_path_core_lists_direct_children(client):
    assert await _get(client, f"{OPERATIONAL}/$path", level="core") == [
        "Temperature", "Motor", "Setpoints", "Firmware",
    ]


async def test_element_path_includes_itself(client):
    assert await _get(client, f"{OPERATIONAL}/submodel-elements/Motor/$path") == [
        "Motor", "Motor.Speed", "Motor.Status", "Motor.Status.Running",
    ]
    assert await _get(client, f"{OPERATIONAL}/submodel-elements/Motor/$path", level="core") == [
        "Motor", "Motor.Speed", "Motor.Status",
    ]
    assert await _get(client, f"{OPERATIONAL}/submodel-elements/Motor.Speed/$path") == ["Motor.Speed"]


async def test_entity_statements_in_path(client):
    assert await _get(client, f"{SHOWCASE}/submodel-elements/Gripper/$path") == ["Gripper", "Gripper.Force"]


async def test_all_submodel_elements_path(client):
    body = await _get(client, f"{OPERATIONAL}/submodel-elements/$path", limit=2)
    assert body["result"] == ["Temperature", "Motor", "Motor.Speed", "Motor.Status", "Motor.Status.Running"]

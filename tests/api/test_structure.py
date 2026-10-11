"""
Parte 6 — escrita estrutural (POST/PUT/PATCH/DELETE de submodelos e
elementos), sincronizada com o address space OPC UA.
"""
import pytest
from asyncua.common.methods import uamethod

from .conftest import AAS_ID, NAMEPLATE_ID, OPERATIONAL_ID, OTHER_AAS_ID, SHOWCASE_ID, encode


OPERATIONAL = f"/submodels/{encode(OPERATIONAL_ID)}"
NAMEPLATE = f"/submodels/{encode(NAMEPLATE_ID)}"
SHOWCASE = f"/submodels/{encode(SHOWCASE_ID)}"


def prop(id_short, value_type="xs:string", value=None, **extra):
    element = {"modelType": "Property", "idShort": id_short, "valueType": value_type, **extra}
    if value is not None:
        element["value"] = value
    return element


async def child_names(node):
    return {(await child.raw.read_browse_name()).Name for child in await node.get_children()}


async def node_exists(node) -> bool:
    try:
        await node.raw.read_browse_name()
        return True
    except Exception:
        return False


def error_text(response) -> str:
    return response.json()["messages"][0]["text"]


# -----------------------------------------------------------------------------
# POST — elementos
# -----------------------------------------------------------------------------

async def test_post_element_creates_model_and_opcua_nodes(client, registry):
    response = await client.post(f"{NAMEPLATE}/submodel-elements", json=prop("SerialNumber", value="SN-42"))

    assert response.status_code == 201
    assert response.headers["location"].endswith(f"{NAMEPLATE}/submodel-elements/SerialNumber")
    assert response.json()["value"] == "SN-42"

    assert (await client.get(f"{NAMEPLATE}/submodel-elements/SerialNumber/$value")).json() == "SN-42"

    submodel_node = registry.get_element_node(NAMEPLATE_ID, "")
    assert "SerialNumber" in await child_names(submodel_node)
    assert await registry.get_value_node(NAMEPLATE_ID, "SerialNumber").node.get_value() == "SN-42"


async def test_created_property_is_live(client, registry):
    await client.post(f"{NAMEPLATE}/submodel-elements", json=prop("Counter", "xs:long", "1"))

    assert (await client.patch(f"{NAMEPLATE}/submodel-elements/Counter/$value", json=7)).status_code == 204
    assert await registry.get_value_node(NAMEPLATE_ID, "Counter").node.get_value() == 7


async def test_post_element_by_path_into_collection(client, registry):
    response = await client.post(f"{OPERATIONAL}/submodel-elements/Motor", json=prop("Torque", "xs:double", "1.5"))

    assert response.status_code == 201
    assert response.headers["location"].endswith("/submodel-elements/Motor.Torque")
    assert "Torque" in await child_names(registry.get_element_node(OPERATIONAL_ID, "Motor"))
    assert (await client.get(f"{OPERATIONAL}/submodel-elements/Motor.Torque/$value")).json() == 1.5


async def test_post_collection_with_children_and_operation(client, registry):
    body = {
        "modelType": "SubmodelElementCollection",
        "idShort": "Spindle",
        "value": [
            prop("Rpm", "xs:int", "10"),
            {"modelType": "Operation", "idShort": "Stop"},
        ],
    }
    assert (await client.post(f"{OPERATIONAL}/submodel-elements", json=body)).status_code == 201

    assert registry.get_value_node(OPERATIONAL_ID, "Spindle.Rpm") is not None
    assert registry.get_operation(OPERATIONAL_ID, "Spindle.Stop") is not None
    # Operation nova ainda sem método de extensão vinculado
    url = f"{OPERATIONAL}/submodel-elements/Spindle.Stop/invoke"
    assert (await client.post(url, json={})).status_code == 501


async def test_post_into_list_appends_at_the_end(client):
    item = prop("Setpoint2", "xs:double", "30.0")
    response = await client.post(f"{OPERATIONAL}/submodel-elements/Setpoints", json=item)

    assert response.status_code == 201
    assert response.headers["location"].endswith("/submodel-elements/Setpoints%5B2%5D")
    assert (await client.get(f"{OPERATIONAL}/submodel-elements/Setpoints/$value")).json() == [10.0, 20.0, 30.0]


@pytest.mark.parametrize("url, body, status", [
    (f"{NAMEPLATE}/submodel-elements", prop("ManufacturerName"), 409),
    (f"{NAMEPLATE}/submodel-elements", {"modelType": "Property", "valueType": "xs:string"}, 400),
    (f"{NAMEPLATE}/submodel-elements", {"modelType": "Property", "idShort": "NoType"}, 400),
    (f"{NAMEPLATE}/submodel-elements", {"modelType": "Bogus", "idShort": "X"}, 400),
    (f"{NAMEPLATE}/submodel-elements", ["not", "an", "object"], 400),
    (f"{OPERATIONAL}/submodel-elements/Temperature", prop("X"), 400),
    (f"{OPERATIONAL}/submodel-elements/Missing", prop("X"), 404),
])
async def test_post_element_errors(client, url, body, status):
    assert (await client.post(url, json=body)).status_code == status


# -----------------------------------------------------------------------------
# POST — submodelos
# -----------------------------------------------------------------------------

NEW_SUBMODEL_ID = "urn:faaster:test:sm:maintenance"


def new_submodel(**extra):
    return {
        "modelType": "Submodel",
        "id": NEW_SUBMODEL_ID,
        "idShort": "Maintenance",
        "submodelElements": [prop("Hours", "xs:int", "12")],
        **extra,
    }


async def test_post_submodel(client, registry):
    response = await client.post("/submodels", json=new_submodel())

    assert response.status_code == 201
    assert response.headers["location"].endswith(f"/submodels/{encode(NEW_SUBMODEL_ID)}")
    assert response.json()["idShort"] == "Maintenance"

    assert (await client.get(f"/submodels/{encode(NEW_SUBMODEL_ID)}/$value")).json() == {"Hours": 12}
    assert registry.get_element_node(NEW_SUBMODEL_ID, "") is not None
    assert await registry.get_value_node(NEW_SUBMODEL_ID, "Hours").node.get_value() == 12

    serialized = (await client.get("/serialization", params={"submodelIds": encode(NEW_SUBMODEL_ID)})).json()
    assert serialized["submodels"][0]["id"] == NEW_SUBMODEL_ID


async def test_post_submodel_conflict_and_invalid(client):
    assert (await client.post("/submodels", json=new_submodel())).status_code == 201
    assert (await client.post("/submodels", json=new_submodel())).status_code == 409
    assert (await client.post("/submodels", json={"modelType": "Submodel"})).status_code == 400


# -----------------------------------------------------------------------------
# PUT — elementos
# -----------------------------------------------------------------------------

async def test_put_same_structure_updates_in_place(client, registry):
    motor_node = registry.get_element_node(OPERATIONAL_ID, "Motor")
    speed_node = registry.get_value_node(OPERATIONAL_ID, "Motor.Speed").node

    motor = (await client.get(f"{OPERATIONAL}/submodel-elements/Motor")).json()
    motor["description"] = [{"language": "en", "text": "Main drive"}]
    motor["value"][0]["value"] = "1500"           # Speed

    response = await client.put(f"{OPERATIONAL}/submodel-elements/Motor", json=motor)

    assert response.status_code == 204
    # mesmos nós: NodeIds, assinaturas e HDA preservados
    assert registry.get_element_node(OPERATIONAL_ID, "Motor") is motor_node
    assert registry.get_value_node(OPERATIONAL_ID, "Motor.Speed").node is speed_node
    assert await speed_node.get_value() == 1500
    assert "Description" in await child_names(motor_node)

    served = (await client.get(f"{OPERATIONAL}/submodel-elements/Motor")).json()
    assert served["description"] == [{"language": "en", "text": "Main drive"}]


async def test_put_new_structure_rebuilds_nodes(client, registry):
    old_node = registry.get_value_node(OPERATIONAL_ID, "Motor.Speed").node

    response = await client.put(
        f"{OPERATIONAL}/submodel-elements/Motor.Speed", json=prop("Speed", "xs:double", "12.5")
    )

    assert response.status_code == 204
    new_entry = registry.get_value_node(OPERATIONAL_ID, "Motor.Speed")
    assert new_entry.node.node_id != old_node.node_id
    assert not await node_exists(old_node)
    assert await new_entry.node.get_value() == 12.5
    assert (await client.get(f"{OPERATIONAL}/submodel-elements/Motor.Speed/$value")).json() == 12.5


async def test_put_creates_missing_element(client, registry):
    response = await client.put(f"{NAMEPLATE}/submodel-elements/Country", json=prop("Country", value="BR"))

    assert response.status_code == 201
    assert response.json()["value"] == "BR"
    assert registry.get_value_node(NAMEPLATE_ID, "Country") is not None


async def test_put_requires_matching_id_short(client):
    response = await client.put(f"{NAMEPLATE}/submodel-elements/ManufacturerName", json=prop("Other"))
    assert response.status_code == 400


async def test_put_historized_property_in_place(client, registry):
    node = registry.get_value_node(OPERATIONAL_ID, "Temperature").node
    body = (await client.get(f"{OPERATIONAL}/submodel-elements/Temperature")).json()
    body["description"] = [{"language": "pt", "text": "Temperatura"}]
    body["value"] = "30.5"

    response = await client.put(f"{OPERATIONAL}/submodel-elements/Temperature", json=body)

    assert response.status_code == 204
    assert registry.get_value_node(OPERATIONAL_ID, "Temperature").node is node
    assert await node.get_value() == 30.5


async def test_put_historized_property_new_type_is_conflict(client, registry):
    body = (await client.get(f"{OPERATIONAL}/submodel-elements/Temperature")).json()
    body["valueType"] = "xs:float"

    response = await client.put(f"{OPERATIONAL}/submodel-elements/Temperature", json=body)

    assert response.status_code == 409
    assert "Temperature (historized)" in error_text(response)
    assert (await client.get(f"{OPERATIONAL}/submodel-elements/Temperature")).json()["valueType"] == "xs:double"


async def test_put_invalid_value_changes_nothing(client, registry):
    body = (await client.get(f"{OPERATIONAL}/submodel-elements/Motor")).json()
    body["description"] = [{"language": "en", "text": "x"}]
    body["value"][0]["value"] = "fast"

    assert (await client.put(f"{OPERATIONAL}/submodel-elements/Motor", json=body)).status_code == 400
    assert "description" not in (await client.get(f"{OPERATIONAL}/submodel-elements/Motor")).json()


# -----------------------------------------------------------------------------
# PATCH — normal (level=core) e $metadata
# -----------------------------------------------------------------------------

async def test_patch_metadata_keeps_live_value_and_node(client, registry):
    node = registry.get_value_node(OPERATIONAL_ID, "Temperature").node
    await client.patch(f"{OPERATIONAL}/submodel-elements/Temperature/$value", json=55.5)

    metadata = (await client.get(f"{OPERATIONAL}/submodel-elements/Temperature/$metadata")).json()
    metadata["description"] = [{"language": "en", "text": "Oil temperature"}]
    response = await client.patch(f"{OPERATIONAL}/submodel-elements/Temperature/$metadata", json=metadata)

    assert response.status_code == 204
    assert registry.get_value_node(OPERATIONAL_ID, "Temperature").node is node
    served = (await client.get(f"{OPERATIONAL}/submodel-elements/Temperature")).json()
    assert served["value"] == "55.5"
    assert served["description"][0]["text"] == "Oil temperature"


async def test_patch_metadata_rebuild_preserves_live_value(client, registry):
    # categoria nova exige recriar o nó; o valor vivo é levado para o nó novo
    url = f"{NAMEPLATE}/submodel-elements/ManufacturerName"
    await client.patch(f"{url}/$value", json="Open AAS")
    old_node = registry.get_value_node(NAMEPLATE_ID, "ManufacturerName").node

    metadata = (await client.get(f"{url}/$metadata")).json()
    metadata["category"] = "PARAMETER"
    assert (await client.patch(f"{url}/$metadata", json=metadata)).status_code == 204

    new_node = registry.get_value_node(NAMEPLATE_ID, "ManufacturerName").node
    assert new_node.node_id != old_node.node_id
    assert await new_node.get_value() == "Open AAS"


async def test_patch_collection_metadata_keeps_children(client, registry):
    speed_node = registry.get_value_node(OPERATIONAL_ID, "Motor.Speed").node
    await client.patch(f"{OPERATIONAL}/submodel-elements/Motor.Speed/$value", json=777)

    response = await client.patch(
        f"{OPERATIONAL}/submodel-elements/Motor/$metadata",
        json={"modelType": "SubmodelElementCollection", "idShort": "Motor", "category": "PARAMETER"},
    )

    assert response.status_code == 204
    assert registry.get_value_node(OPERATIONAL_ID, "Motor.Speed").node is speed_node
    assert await speed_node.get_value() == 777
    assert (await client.get(f"{OPERATIONAL}/submodel-elements/Motor")).json()["category"] == "PARAMETER"


async def test_patch_core_ignores_children_in_body(client, registry):
    body = {"modelType": "SubmodelElementCollection", "idShort": "Motor", "value": [prop("Ghost")]}

    assert (await client.patch(f"{OPERATIONAL}/submodel-elements/Motor", json=body)).status_code == 204
    paths = (await client.get(f"{OPERATIONAL}/submodel-elements/Motor/$path")).json()
    assert "Motor.Ghost" not in paths
    assert "Motor.Speed" in paths


async def test_patch_property_writes_value(client, registry):
    body = prop("ManufacturerName", value="Patched")
    assert (await client.patch(f"{NAMEPLATE}/submodel-elements/ManufacturerName", json=body)).status_code == 204
    assert await registry.get_value_node(NAMEPLATE_ID, "ManufacturerName").node.get_value() == "Patched"


@pytest.mark.parametrize("suffix, body", [
    ("", {"modelType": "Range", "idShort": "ManufacturerName"}),
    ("", prop("Renamed")),
    ("?level=deep", prop("ManufacturerName")),
    ("/$metadata", {"modelType": "Range"}),
])
async def test_patch_element_errors(client, suffix, body):
    url = f"{NAMEPLATE}/submodel-elements/ManufacturerName{suffix}"
    assert (await client.patch(url, json=body)).status_code == 400


# -----------------------------------------------------------------------------
# DELETE — elementos
# -----------------------------------------------------------------------------

async def test_delete_element_removes_model_and_nodes(client, registry):
    status_node = registry.get_element_node(OPERATIONAL_ID, "Motor.Status")

    response = await client.delete(f"{OPERATIONAL}/submodel-elements/Motor.Status")

    assert response.status_code == 204
    assert (await client.get(f"{OPERATIONAL}/submodel-elements/Motor.Status")).status_code == 404
    assert not await node_exists(status_node)
    assert registry.get_element_node(OPERATIONAL_ID, "Motor.Status") is None
    assert registry.get_value_node(OPERATIONAL_ID, "Motor.Status.Running") is None


async def test_delete_last_child_drops_empty_list(client):
    assert (await client.delete(f"{OPERATIONAL}/submodel-elements/Motor.Status.Running")).status_code == 204
    status = (await client.get(f"{OPERATIONAL}/submodel-elements/Motor.Status")).json()
    assert "value" not in status


async def test_delete_historized_property_is_conflict(client):
    response = await client.delete(f"{OPERATIONAL}/submodel-elements/Temperature")

    assert response.status_code == 409
    assert (await client.get(f"{OPERATIONAL}/submodel-elements/Temperature")).status_code == 200


async def test_delete_bound_operation_is_conflict(client, registry):
    registry.get_operation(SHOWCASE_ID, "Add").binder.bind(uamethod(lambda parent, a, b: a + b))

    response = await client.delete(f"{SHOWCASE}/submodel-elements/Add")

    assert response.status_code == 409
    assert "Add (bound operation)" in error_text(response)


async def test_delete_unbound_operation(client, registry):
    assert (await client.delete(f"{SHOWCASE}/submodel-elements/Reset")).status_code == 204
    assert registry.get_operation(SHOWCASE_ID, "Reset") is None
    assert [op.id_short for op in registry.get_operations("Showcase")] == ["Add", "Swap", "Echo"]


async def test_delete_missing_element_is_not_found(client):
    assert (await client.delete(f"{NAMEPLATE}/submodel-elements/Missing")).status_code == 404


# -----------------------------------------------------------------------------
# PUT / PATCH / DELETE — submodelos
# -----------------------------------------------------------------------------

async def test_put_submodel_same_structure_in_place(client, registry):
    node = registry.get_element_node(OPERATIONAL_ID, "")
    body = (await client.get(OPERATIONAL)).json()
    body["description"] = [{"language": "en", "text": "Live data"}]

    assert (await client.put(OPERATIONAL, json=body)).status_code == 204
    assert registry.get_element_node(OPERATIONAL_ID, "") is node
    assert (await client.get(OPERATIONAL)).json()["description"][0]["text"] == "Live data"


async def test_put_submodel_reconciles_children(client, registry):
    submodel_node = registry.get_element_node(NAMEPLATE_ID, "")
    removed = registry.get_element_node(NAMEPLATE_ID, "ManufacturerName")
    body = {"modelType": "Submodel", "id": NAMEPLATE_ID, "idShort": "Nameplate", "submodelElements": [prop("Model", value="X1")]}

    assert (await client.put(NAMEPLATE, json=body)).status_code == 204
    # só os filhos mudam: o nó do submodelo é mantido
    assert registry.get_element_node(NAMEPLATE_ID, "") is submodel_node
    assert not await node_exists(removed)
    assert registry.get_value_node(NAMEPLATE_ID, "ManufacturerName") is None
    assert await child_names(submodel_node) >= {"Model"}
    assert (await client.get(f"{NAMEPLATE}/$value")).json() == {"Model": "X1"}


async def test_put_submodel_new_id_short_rebuilds(client, registry):
    old = registry.get_element_node(NAMEPLATE_ID, "")
    body = (await client.get(NAMEPLATE)).json()
    body["idShort"] = "Typeplate"

    assert (await client.put(NAMEPLATE, json=body)).status_code == 204
    assert not await node_exists(old)
    assert (await registry.get_element_node(NAMEPLATE_ID, "").raw.read_browse_name()).Name == "Typeplate"


async def test_put_submodel_without_blob_value_keeps_historized_nodes(client, registry):
    # o GET omite o valor do Blob (withoutBlobValue); o Blob não tem nó OPC UA,
    # então devolver o corpo com outra descrição não toca na Temperature
    node = registry.get_value_node(OPERATIONAL_ID, "Temperature").node
    body = (await client.get(OPERATIONAL)).json()
    body["submodelElements"][0]["description"] = [{"language": "en", "text": "t"}]

    assert (await client.put(OPERATIONAL, json=body)).status_code == 204
    assert registry.get_value_node(OPERATIONAL_ID, "Temperature").node is node


async def test_put_submodel_with_historized_property_new_structure_is_conflict(client):
    body = (await client.get(OPERATIONAL)).json()
    body["submodelElements"] = [e for e in body["submodelElements"] if e["idShort"] != "Temperature"]

    assert (await client.put(OPERATIONAL, json=body)).status_code == 409


async def test_put_submodel_creates_and_checks_id(client):
    response = await client.put(f"/submodels/{encode(NEW_SUBMODEL_ID)}", json=new_submodel())
    assert response.status_code == 201

    other = new_submodel(id="urn:other")
    assert (await client.put(f"/submodels/{encode(NEW_SUBMODEL_ID)}", json=other)).status_code == 400


async def test_patch_submodel_metadata_on_historized_submodel(client, registry):
    response = await client.patch(
        f"{OPERATIONAL}/$metadata",
        json={"modelType": "Submodel", "id": OPERATIONAL_ID, "idShort": "OperationalData", "category": "VARIABLE"},
    )

    assert response.status_code == 204
    assert (await client.get(OPERATIONAL)).json()["category"] == "VARIABLE"
    # elementos intactos
    assert len((await client.get(f"{OPERATIONAL}/$path")).json()) > 1


async def test_delete_submodel(client, registry):
    node = registry.get_element_node(NAMEPLATE_ID, "")

    assert (await client.delete(NAMEPLATE)).status_code == 204
    assert (await client.get(NAMEPLATE)).status_code == 404
    assert not await node_exists(node)


async def test_delete_submodel_with_historized_property_is_conflict(client):
    assert (await client.delete(OPERATIONAL)).status_code == 409


async def test_delete_via_superpath_removes_reference(client):
    url = f"/shells/{encode(OTHER_AAS_ID)}/submodels/{encode(NAMEPLATE_ID)}"
    assert (await client.delete(url)).status_code == 204

    refs = (await client.get(f"/shells/{encode(OTHER_AAS_ID)}")).json().get("submodels", [])
    assert all(r["keys"][-1]["value"] != NAMEPLATE_ID for r in refs)


async def test_superpath_put_requires_referenced_submodel(client):
    url = f"/shells/{encode(OTHER_AAS_ID)}/submodels/{encode(NEW_SUBMODEL_ID)}"
    assert (await client.put(url, json=new_submodel())).status_code == 404


async def test_superpath_post_element(client, registry):
    url = f"/shells/{encode(AAS_ID)}/submodels/{encode(NAMEPLATE_ID)}/submodel-elements"
    response = await client.post(url, json=prop("Batch", value="B7"))

    assert response.status_code == 201
    assert f"/shells/{encode(AAS_ID)}/submodels/" in response.headers["location"]


async def test_property_without_value_gets_typed_null_node(client, registry):
    # value é opcional no AAS; antes o nó numérico sem valor derrubava o parser
    response = await client.post(f"{NAMEPLATE}/submodel-elements", json=prop("Weight", "xs:int"))

    assert response.status_code == 201
    entry = registry.get_value_node(NAMEPLATE_ID, "Weight")
    assert await entry.node.get_value() is None
    assert (await client.patch(f"{NAMEPLATE}/submodel-elements/Weight/$value", json=12)).status_code == 204
    assert await entry.node.get_value() == 12

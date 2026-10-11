"""
AAS Repository (SSP-002), superpath /shells/{aas}/submodels/{sm}/...,
Concept Description Repository (leitura) e /serialization.
"""
import json

from faaster.api.encoding import b64url_encode
from faaster.api.profiles import AAS_REPOSITORY_READ
from faaster.parser.creators.base import resolve_variant_type

from .conftest import (
    AAS_ID,
    CD_CELSIUS_ID,
    CD_TEMPERATURE_ID,
    CD_UNUSED_ID,
    NAMEPLATE_ID,
    OPERATIONAL_ID,
    OTHER_AAS_ID,
    SHOWCASE_ID,
    encode,
)


SHELL = f"/shells/{encode(AAS_ID)}"


async def _get(client, url, **params):
    # params={} faria o httpx descartar a query string já montada na URL
    response = await client.get(url, params=params or None)
    assert response.status_code == 200, response.text
    return response.json()


async def _get_error(client, url, status, **params):
    response = await client.get(url, params=params or None)
    assert response.status_code == status, response.text
    assert response.json()["messages"][0]["code"] == str(status)


def _asset_id(name, value):
    return b64url_encode(json.dumps({"name": name, "value": value}))


async def test_description_declares_aas_repository_read(client):
    assert AAS_REPOSITORY_READ in (await _get(client, "/description"))["profiles"]


# =============================================================================
# /shells
# =============================================================================

async def test_get_all_shells(client):
    body = await _get(client, "/shells")
    assert [s["id"] for s in body["result"]] == [AAS_ID, OTHER_AAS_ID]


async def test_get_all_shells_pagination(client):
    first = await _get(client, "/shells", limit=1)
    second = await _get(client, "/shells", cursor=first["paging_metadata"]["cursor"])
    assert [s["id"] for s in second["result"]] == [OTHER_AAS_ID]


async def test_get_all_shells_filter_by_id_short(client):
    body = await _get(client, "/shells", idShort="OtherAAS")
    assert [s["id"] for s in body["result"]] == [OTHER_AAS_ID]


async def test_get_all_shells_filter_by_global_asset_id(client):
    body = await _get(client, "/shells", assetIds=_asset_id("globalAssetId", "urn:faaster:test:asset:2"))
    assert [s["id"] for s in body["result"]] == [OTHER_AAS_ID]


async def test_get_all_shells_asset_ids_must_all_match(client):
    url = "/shells?assetIds={}&assetIds={}"
    both = url.format(
        _asset_id("globalAssetId", "urn:faaster:test:asset:1"),
        _asset_id("serialNumber", "SN-001"),
    )
    assert [s["id"] for s in (await _get(client, both))["result"]] == [AAS_ID]

    mismatch = url.format(
        _asset_id("globalAssetId", "urn:faaster:test:asset:1"),
        _asset_id("serialNumber", "SN-999"),
    )
    assert (await _get(client, mismatch))["result"] == []


async def test_get_all_shells_rejects_malformed_asset_id(client):
    await _get_error(client, "/shells", 400, assetIds=b64url_encode("not json"))


async def test_get_all_shells_reference(client):
    body = await _get(client, "/shells/$reference")
    assert body["result"][0] == {
        "type": "ModelReference",
        "keys": [{"type": "AssetAdministrationShell", "value": AAS_ID}],
    }


async def test_get_shell_by_id(client):
    body = await _get(client, SHELL)
    assert body["idShort"] == "TestAAS"
    assert body["assetInformation"]["globalAssetId"] == "urn:faaster:test:asset:1"


async def test_get_shell_by_id_not_found(client):
    await _get_error(client, f"/shells/{encode('urn:unknown')}", 404)


async def test_get_shell_reference(client):
    body = await _get(client, f"{SHELL}/$reference")
    assert body["keys"] == [{"type": "AssetAdministrationShell", "value": AAS_ID}]


async def test_get_asset_information(client):
    body = await _get(client, f"{SHELL}/asset-information")
    assert body["specificAssetIds"] == [{"name": "serialNumber", "value": "SN-001"}]


async def test_get_submodel_refs(client):
    body = await _get(client, f"{SHELL}/submodel-refs", limit=2)
    assert [r["keys"][0]["value"] for r in body["result"]] == [OPERATIONAL_ID, NAMEPLATE_ID]
    rest = await _get(client, f"{SHELL}/submodel-refs", cursor=body["paging_metadata"]["cursor"])
    assert [r["keys"][0]["value"] for r in rest["result"]] == [SHOWCASE_ID]


# =============================================================================
# Superpath /shells/{aas}/submodels/{sm}/...
# =============================================================================

async def test_superpath_submodel(client):
    body = await _get(client, f"{SHELL}/submodels/{encode(NAMEPLATE_ID)}")
    assert body["idShort"] == "Nameplate"


async def test_superpath_rejects_submodel_not_referenced_by_shell(client):
    # OtherAAS só referencia o Nameplate
    other = f"/shells/{encode(OTHER_AAS_ID)}"
    await _get_error(client, f"{other}/submodels/{encode(OPERATIONAL_ID)}", 404)
    await _get_error(client, f"{other}/submodels/{encode(OPERATIONAL_ID)}/submodel-elements/Motor", 404)
    assert (await client.get(f"{other}/submodels/{encode(NAMEPLATE_ID)}")).status_code == 200


async def test_superpath_element_with_live_value_and_modifiers(client, registry):
    entry = registry.get_value_node(OPERATIONAL_ID, "Motor.Speed")
    await entry.node.set_value(777, resolve_variant_type(entry.value_type))

    base = f"{SHELL}/submodels/{encode(OPERATIONAL_ID)}/submodel-elements"
    assert (await _get(client, f"{base}/Motor.Speed"))["value"] == "777"
    assert await _get(client, f"{base}/Motor.Speed/$value") == 777
    assert await _get(client, f"{base}/Motor/$path", level="core") == ["Motor", "Motor.Speed", "Motor.Status"]
    assert (await _get(client, f"{base}/$metadata"))["result"][0]["idShort"] == "Temperature"


async def test_superpath_operation_ids_follow_spec(client):
    spec = await _get(client, "/openapi.json")
    operation_ids = {
        op["operationId"]
        for path in spec["paths"].values()
        for op in path.values()
    }
    assert {
        "GetSubmodelById_AasRepository",
        "GetSubmodelElementByPath-ValueOnly_AasRepository",
        "GetSubmodelById",
        "GetSubmodelElementByPath-ValueOnly_SubmodelRepo",
        "GetAllAssetAdministrationShells",
        "GetAllConceptDescriptions",
        "GenerateSerializationByIds",
    } <= operation_ids


# =============================================================================
# /concept-descriptions
# =============================================================================

async def test_get_all_concept_descriptions(client):
    body = await _get(client, "/concept-descriptions")
    assert [c["id"] for c in body["result"]] == [CD_TEMPERATURE_ID, CD_CELSIUS_ID, CD_UNUSED_ID]


async def test_get_all_concept_descriptions_filters(client):
    by_id_short = await _get(client, "/concept-descriptions", idShort="Celsius")
    assert [c["id"] for c in by_id_short["result"]] == [CD_CELSIUS_ID]

    is_case_of = b64url_encode(json.dumps({
        "type": "ExternalReference",
        "keys": [{"type": "GlobalReference", "value": "0173-1#02-AAA001#001"}],
    }))
    body = await _get(client, "/concept-descriptions", isCaseOf=is_case_of)
    assert [c["id"] for c in body["result"]] == [CD_TEMPERATURE_ID]

    data_spec = b64url_encode(json.dumps({
        "type": "ExternalReference",
        "keys": [{
            "type": "GlobalReference",
            "value": "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIec61360/3",
        }],
    }))
    body = await _get(client, "/concept-descriptions", dataSpecificationRef=data_spec)
    assert [c["id"] for c in body["result"]] == [CD_TEMPERATURE_ID]


async def test_get_concept_description_by_id(client):
    body = await _get(client, f"/concept-descriptions/{encode(CD_CELSIUS_ID)}")
    assert body == {"modelType": "ConceptDescription", "id": CD_CELSIUS_ID, "idShort": "Celsius"}


async def test_get_concept_description_not_found(client):
    await _get_error(client, f"/concept-descriptions/{encode('urn:unknown')}", 404)


# =============================================================================
# /serialization
# =============================================================================

async def test_serialization_by_ids_with_indirect_concept_descriptions(client, registry):
    entry = registry.get_value_node(OPERATIONAL_ID, "Temperature")
    await entry.node.set_value(30.0, resolve_variant_type(entry.value_type))

    url = f"/serialization?aasIds={encode(AAS_ID)}&submodelIds={encode(OPERATIONAL_ID)}"
    body = await _get(client, url)

    assert [s["id"] for s in body["assetAdministrationShells"]] == [AAS_ID]
    assert [s["id"] for s in body["submodels"]] == [OPERATIONAL_ID]
    # valor vivo e blob completo
    elements = {e["idShort"]: e for e in body["submodels"][0]["submodelElements"]}
    assert elements["Temperature"]["value"] == "30.0"
    assert elements["Firmware"]["value"] == "AAECAw=="
    # temperature (semanticId) → celsius (valueList); unused fica de fora
    assert [c["id"] for c in body["conceptDescriptions"]] == [CD_TEMPERATURE_ID, CD_CELSIUS_ID]


async def test_serialization_without_concept_descriptions(client):
    url = f"/serialization?submodelIds={encode(OPERATIONAL_ID)}&includeConceptDescriptions=false"
    body = await _get(client, url)
    assert "conceptDescriptions" not in body
    assert "assetAdministrationShells" not in body


async def test_serialization_without_ids_returns_everything(client):
    body = await _get(client, "/serialization")
    assert len(body["assetAdministrationShells"]) == 2
    assert len(body["submodels"]) == 3


async def test_serialization_unknown_id(client):
    await _get_error(client, f"/serialization?submodelIds={encode('urn:unknown')}", 404)


async def test_serialization_xml_not_implemented(client):
    response = await client.get("/serialization", headers={"Accept": "application/xml"})
    assert response.status_code == 501


# =============================================================================
# Fidelidade ao modelo de entrada
# =============================================================================

async def test_loader_document_is_not_mutated_by_validation():
    # alguns modelos pydantic do aas_metamodel alteram dicts aninhados no
    # __init__ (ex.: DataSpecificationIec61360); a API serve o documento intacto
    from faaster.loader.json.loader import JsonLoader
    from .conftest import MODEL

    loader = JsonLoader()
    await loader.load(MODEL)
    assert loader.document == json.loads(MODEL.read_text())


async def test_concept_description_served_as_authored(client):
    from .conftest import MODEL

    authored = json.loads(MODEL.read_text())["conceptDescriptions"][0]
    assert await _get(client, f"/concept-descriptions/{encode(CD_TEMPERATURE_ID)}") == authored

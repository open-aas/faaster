"""Leitura do AID/AIMC a partir do documento (sem rede)."""
from faaster.binding.model import (
    AIMC_SEMANTIC_PREFIX,
    PropertyAffordance,
    id_short_path,
    parse_aid,
    parse_aimc,
    submodel_version,
)

from tests.binding.conftest import AID_SM, FakePlc, IO_SM, build_model, mapping


PLC = FakePlc(url="opc.tcp://plc:4840", ns=2, nodes={})


def _submodel(model, sm_id):
    return next(sm for sm in model["submodels"] if sm["id"] == sm_id)


def test_parse_aid_reads_endpoint_security_and_points():
    [interface] = parse_aid(_submodel(build_model(PLC), AID_SM))

    assert interface.id_short == "InterfaceOPCUA"
    assert interface.base == "opc.tcp://plc:4840"
    assert interface.scheme == "opc.tcp"
    assert interface.security_schemes == ["nosec"]
    assert set(interface.properties) == {"xIn", "rTemp", "xOut"}
    assert interface.properties["xIn"].observable is True
    assert interface.properties["xIn"].browse_path == "2:DeviceSet/2:plcTest/2:Inputs/2:xIn"


def test_node_id_from_href_ignores_placeholders():
    assert PropertyAffordance("a", href="?id=ns=3;s=plc.x").node_id == "ns=3;s=plc.x"
    assert PropertyAffordance("a", href="?id=i=2258").node_id == "i=2258"
    assert PropertyAffordance("a", href="?id=PENDENTE").node_id is None
    assert PropertyAffordance("a", href=None).node_id is None


def test_parse_aid_accepts_legacy_1_0_layout():
    """AID 1.0 dos modelos atuais: forms como lista e security como Property."""
    submodel = {
        "id": "urn:x:aid", "submodelElements": [{
            "idShort": "InterfaceOPCUA", "modelType": "SubmodelElementCollection", "value": [
                {"idShort": "EndpointMetadata", "modelType": "SubmodelElementCollection", "value": [
                    {"idShort": "base", "modelType": "Property", "value": "opc.tcp://plc:4840"},
                    {"idShort": "security", "modelType": "SubmodelElementList", "value": [
                        {"idShort": "nosec", "modelType": "Property", "value": "nosec_sc"}]},
                    {"idShort": "securityDefinitions", "modelType": "SubmodelElementCollection", "value": [
                        {"idShort": "nosec_sc", "modelType": "SubmodelElementCollection", "value": [
                            {"idShort": "scheme", "modelType": "Property", "value": "nosec"}]}]},
                ]},
                {"idShort": "InteractionMetadata", "modelType": "SubmodelElementCollection", "value": [
                    {"idShort": "properties", "modelType": "SubmodelElementCollection", "value": [
                        {"idShort": "BG1", "modelType": "SubmodelElementCollection", "value": [
                            {"idShort": "forms", "modelType": "SubmodelElementList", "value": [
                                {"idShort": "form0", "modelType": "SubmodelElementCollection", "value": [
                                    {"idShort": "href", "modelType": "Property",
                                     "value": "2:DeviceSet/3:plc/3:Inputs/3:xBG1"}]}]}]}]}]},
            ]}],
    }
    [interface] = parse_aid(submodel)
    assert interface.security_schemes == ["nosec"]
    assert interface.properties["BG1"].href == "2:DeviceSet/3:plc/3:Inputs/3:xBG1"


def test_parse_aimc_pairs_sources_and_sinks():
    model = build_model(PLC)
    aimc = next(sm for sm in model["submodels"] if sm["idShort"] == "AssetInterfacesMappingConfiguration")
    north, south = parse_aimc(aimc)

    assert [s.id for s in north.sources] == ["xIn", "rTemp", "xOut"]
    assert north.sinks[0].keys[0] == ("Submodel", IO_SM)
    assert south.sources[0].keys[-1] == ("Property", "Out")
    assert not north.has_transformation


def test_transformation_is_detected():
    m = mapping([("a", [("Submodel", "x")], [("Submodel", "y")])], transformation="function aimc_main(s) end")
    model = build_model(PLC, mappings=[m])
    aimc = model["submodels"][-1]
    [config] = parse_aimc(aimc)
    assert config.has_transformation


def test_id_short_path_and_version():
    keys = [("Submodel", "s"), ("SubmodelElementCollection", "A"),
            ("SubmodelElementList", "L"), ("SubmodelElementCollection", "0"), ("Property", "P")]
    assert id_short_path(keys) == "A.L[0].P"
    assert submodel_version(AIMC_SEMANTIC_PREFIX + "2/0/Submodel", AIMC_SEMANTIC_PREFIX) == (2, 0)

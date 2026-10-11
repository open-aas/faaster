"""
Modelo AAS com os elementos estruturais (listas, entidades, relacionamentos,
capability e blob), compartilhado pelos testes do parser e da API.
"""
import json
from pathlib import Path


SUBMODEL_ID = "urn:faaster:test:sm:structures"
AAS_ID = "urn:faaster:test:aas:structures"


def reference(*keys):
    return {"type": "ModelReference", "keys": [{"type": t, "value": v} for t, v in keys]}


def prop(id_short=None, value="0", value_type="xs:double", **extra):
    element = {"modelType": "Property", "valueType": value_type, "value": value, **extra}
    if id_short:
        element["idShort"] = id_short
    return element


SUBMODEL = {
    "modelType": "Submodel",
    "id": SUBMODEL_ID,
    "idShort": "Structures",
    "submodelElements": [
        {
            "modelType": "SubmodelElementList",
            "idShort": "Setpoints",
            "orderRelevant": True,
            "typeValueListElement": "Property",
            "valueTypeListElement": "xs:double",
            "semanticIdListElement": {
                "type": "ExternalReference",
                "keys": [{"type": "GlobalReference", "value": "urn:faaster:test:setpoint"}],
            },
            "value": [prop(value="10"), prop(value="20"), prop(value="30")],
        },
        {
            "modelType": "SubmodelElementList",
            "idShort": "Layers",
            "typeValueListElement": "SubmodelElementCollection",
            "value": [
                {"modelType": "SubmodelElementCollection", "value": [prop("Thickness", "1.5")]},
                {"modelType": "SubmodelElementCollection", "value": [prop("Thickness", "2.5")]},
            ],
        },
        {
            "modelType": "Entity",
            "idShort": "Motor",
            "entityType": "SelfManagedEntity",
            "globalAssetId": "urn:faaster:test:asset:motor",
            "specificAssetIds": [{"name": "serialNumber", "value": "M-001"}],
            "description": [{"language": "en", "text": "Drive motor"}],
            "statements": [
                prop("Power", "1.5"),
                {"modelType": "SubmodelElementCollection", "idShort": "Plate", "value": [prop("Rpm", "1750", "xs:long")]},
            ],
        },
        {
            "modelType": "RelationshipElement",
            "idShort": "Drives",
            "first": reference(("Submodel", SUBMODEL_ID), ("Entity", "Motor")),
            "second": reference(("Submodel", SUBMODEL_ID), ("SubmodelElementList", "Layers")),
        },
        {
            "modelType": "AnnotatedRelationshipElement",
            "idShort": "Mounted",
            "first": reference(("Submodel", SUBMODEL_ID), ("Entity", "Motor")),
            "second": reference(("Submodel", SUBMODEL_ID), ("SubmodelElementList", "Setpoints")),
            "annotations": [prop("Torque", "3.0")],
        },
        {
            "modelType": "Capability",
            "idShort": "Welding",
            "semanticId": reference(("ConceptDescription", "urn:faaster:test:cd:welding")),
        },
        {
            "modelType": "Blob",
            "idShort": "Firmware",
            "contentType": "application/octet-stream",
            "value": "AAEC",
        },
    ],
}


MODEL = {
    "assetAdministrationShells": [{
        "modelType": "AssetAdministrationShell",
        "id": AAS_ID,
        "idShort": "StructuresAAS",
        "assetInformation": {"assetKind": "Instance", "globalAssetId": "urn:faaster:test:asset:structures"},
        "submodels": [reference(("Submodel", SUBMODEL_ID))],
    }],
    "submodels": [SUBMODEL],
    "conceptDescriptions": [],
}


def write_model(directory: Path, model=MODEL) -> Path:
    path = directory / "structures.json"
    path.write_text(json.dumps(model))
    return path

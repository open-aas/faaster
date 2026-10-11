"""
Fixtures do vínculo AID/AIMC.

`plc` sobe um servidor OPC UA real em localhost no papel do CLP, com a
mesma organização dos CLPs da CP-L-406-1 (DeviceSet/<plc>/Inputs|Outputs).
`build_model` gera um ambiente AAS com IOInterface, AID 1.2 e AIMC 2.x.
"""
import asyncio
import json
import socket
from argparse import Namespace
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pytest
from asyncua import Node, Server, ua

from faaster.asset_administration_shell import AssetAdministrationShell


PLC_NS = "urn:faaster:test:plc"
AID_SM = "urn:faaster:test:sm:aid"
AIMC_SM = "urn:faaster:test:sm:aimc"
IO_SM = "urn:faaster:test:sm:io"

AID_SEMANTIC = "https://admin-shell.io/idta/AssetInterfacesDescription/1/2/Submodel"
AIMC_SEMANTIC = "https://admin-shell.io/idta/AssetInterfacesMappingConfiguration/2/0/Submodel"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def wait_for(predicate, timeout: float = 5.0) -> None:
    """Espera uma condição assíncrona ficar verdadeira."""
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if await predicate():
            return
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.02)


@dataclass
class FakePlc:
    url: str
    ns: int
    nodes: Dict[str, Node]

    async def read(self, name: str) -> Any:
        return await self.nodes[name].read_value()

    async def set(self, name: str, value: Any) -> None:
        await self.nodes[name].write_value(value)


@pytest.fixture
async def plc():
    port = free_port()
    url = f"opc.tcp://127.0.0.1:{port}"
    server = Server()
    await server.init()
    server.set_endpoint(url)
    ns = await server.register_namespace(PLC_NS)

    device_set = await server.nodes.objects.add_folder(ns, "DeviceSet")
    device = await device_set.add_object(ns, "plcTest")
    inputs = await device.add_folder(ns, "Inputs")
    outputs = await device.add_folder(ns, "Outputs")
    nodes = {
        "xIn": await inputs.add_variable(ns, "xIn", False, ua.VariantType.Boolean),
        "rTemp": await inputs.add_variable(
            ua.NodeId("plcTest.rTemp", ns), ua.QualifiedName("rTemp", ns), 20.0, ua.VariantType.Double
        ),
        "xOut": await outputs.add_variable(ns, "xOut", False, ua.VariantType.Boolean),
    }
    for node in nodes.values():
        await node.set_writable(True)

    async with server:
        yield FakePlc(url=url, ns=ns, nodes=nodes)


# -----------------------------------------------------------------------------
# Modelo
# -----------------------------------------------------------------------------

def _gref(value: str) -> Dict[str, Any]:
    return {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": value}]}


def _prop(id_short: str, value: Any, value_type: str = "xs:string", category: Optional[str] = None):
    p = {"idShort": id_short, "modelType": "Property", "valueType": value_type, "value": value}
    if category:
        p["category"] = category
    return p


def _smc(id_short: Optional[str], value: List[Dict[str, Any]]) -> Dict[str, Any]:
    e = {"modelType": "SubmodelElementCollection", "value": value}
    if id_short:
        e["idShort"] = id_short
    return e


def _ref(keys: List[Tuple[str, str]]) -> Dict[str, Any]:
    return {"type": "ModelReference", "keys": [{"type": t, "value": v} for t, v in keys]}


def _ref_element(id_short: Optional[str], keys) -> Dict[str, Any]:
    e = {"modelType": "ReferenceElement", "value": _ref(keys)}
    if id_short:
        e["idShort"] = id_short
    return e


def _sml(id_short: str, items: List[Dict[str, Any]], item_type: str) -> Dict[str, Any]:
    return {"idShort": id_short, "modelType": "SubmodelElementList",
            "typeValueListElement": item_type, "value": items}


def aid_point(name: str, wot_type: str, href: str, browse_path: Optional[str], observable=True):
    form = [_prop("href", href)]
    if browse_path:
        form.append(_prop("uav_browsePath", browse_path))
    return _smc(name, [
        _prop("title", name),
        _prop("type", wot_type),
        _prop("observable", "true" if observable else "false", "xs:boolean"),
        _smc("forms", form),
    ])


def io_path(*names: str) -> List[Tuple[str, str]]:
    keys = [("Submodel", IO_SM)]
    keys += [("SubmodelElementCollection", n) for n in names[:-1]]
    keys.append(("Property", names[-1]))
    return keys


def aid_path(point: str) -> List[Tuple[str, str]]:
    return [("Submodel", AID_SM), ("SubmodelElementCollection", "InterfaceOPCUA"),
            ("SubmodelElementCollection", "InteractionMetadata"),
            ("SubmodelElementCollection", "properties"), ("SubmodelElementCollection", point)]


def mapping(pairs, transformation: Optional[str] = None) -> Dict[str, Any]:
    """pairs: [(id, source_keys, sink_keys)]."""
    value = []
    if transformation:
        value.append({"idShort": "Transformation", "modelType": "Blob",
                      "contentType": "text/plain", "value": transformation})
    value.append(_sml("Sources", [
        _smc(None, [_ref_element("Source", src), _prop("SourceId", ident)]) for ident, src, _ in pairs
    ], "SubmodelElementCollection"))
    value.append(_sml("Sinks", [
        _smc(None, [_ref_element("Sink", snk), _prop("SinkId", ident)]) for ident, _, snk in pairs
    ], "SubmodelElementCollection"))
    return _smc(None, value)


def build_model(plc: FakePlc, north=True, south=True, with_aimc=True, mappings=None,
                aimc_semantic: str = AIMC_SEMANTIC) -> Dict[str, Any]:
    ns = plc.ns
    browse = lambda folder, name: f"{ns}:DeviceSet/{ns}:plcTest/{ns}:{folder}/{ns}:{name}"
    io = {
        "idShort": "IOInterface", "id": IO_SM, "modelType": "Submodel",
        "submodelElements": [
            _smc("Sensors", [
                _prop("In", "false", "xs:boolean", "VARIABLE"),
                _prop("Temp", "0", "xs:double", "VARIABLE"),
            ]),
            _smc("Actuators", [_prop("Out", "false", "xs:boolean", "VARIABLE")]),
        ],
    }
    aid = {
        "idShort": "AssetInterfacesDescription", "id": AID_SM, "modelType": "Submodel",
        "semanticId": _gref(AID_SEMANTIC),
        "submodelElements": [_smc("InterfaceOPCUA", [
            _prop("title", "Test PLC"),
            _smc("EndpointMetadata", [
                _prop("base", plc.url),
                _prop("contentType", "application/octet-stream"),
                _sml("security", [_ref_element(None, [
                    ("Submodel", AID_SM), ("SubmodelElementCollection", "InterfaceOPCUA"),
                    ("SubmodelElementCollection", "EndpointMetadata"),
                    ("SubmodelElementCollection", "securityDefinitions"),
                    ("SubmodelElementCollection", "nosec_sc"),
                ])], "ReferenceElement"),
                _smc("securityDefinitions", [_smc("nosec_sc", [_prop("scheme", "nosec")])]),
            ]),
            _smc("InteractionMetadata", [_smc("properties", [
                aid_point("xIn", "boolean", "?id=PENDENTE", browse("Inputs", "xIn")),
                aid_point("rTemp", "number", f"?id=ns={ns};s=plcTest.rTemp", None),
                aid_point("xOut", "boolean", "?id=PENDENTE", browse("Outputs", "xOut")),
            ])]),
        ])],
    }
    if mappings is None:
        mappings = []
        if north:
            mappings.append(mapping([
                ("xIn", aid_path("xIn"), io_path("Sensors", "In")),
                ("rTemp", aid_path("rTemp"), io_path("Sensors", "Temp")),
                ("xOut", aid_path("xOut"), io_path("Actuators", "Out")),
            ]))
        if south:
            mappings.append(mapping([("xOut", io_path("Actuators", "Out"), aid_path("xOut"))]))
    submodels = [io, aid]
    if with_aimc:
        submodels.append({
            "idShort": "AssetInterfacesMappingConfiguration", "id": AIMC_SM, "modelType": "Submodel",
            "semanticId": _gref(aimc_semantic),
            "submodelElements": [_sml("MappingConfigurations", mappings, "SubmodelElementCollection")],
        })
    return {
        "assetAdministrationShells": [{
            "idShort": "TestStation", "id": "urn:faaster:test:aas:station",
            "modelType": "AssetAdministrationShell",
            "assetInformation": {"assetKind": "Instance", "globalAssetId": "urn:faaster:test:asset"},
            "submodels": [_ref([("Submodel", sm["id"])]) for sm in submodels],
        }],
        "submodels": submodels,
        "conceptDescriptions": [],
    }


@pytest.fixture
async def faaster_with(tmp_path):
    """Monta um Faaster (sem rede) a partir de um modelo; devolve (aas, binder)."""
    started = []

    async def make(model: Dict[str, Any]):
        path = tmp_path / "model.json"
        path.write_text(json.dumps(model))
        aas = AssetAdministrationShell(Namespace(url_database=None, http_port=None))
        server: Server = aas._opcua_server
        await server.init()
        await server.register_namespace("urn:faaster:server")
        aas.address_space.set_namespace("urn:faaster:server")
        await aas.parser.parse(str(path))
        binder = aas._asset_binder
        binder.configure(aas.parser.document)
        started.append((server, binder))
        return aas, binder

    yield make
    for server, binder in started:
        await binder.stop()
        await server.iserver.stop()


async def aas_value(aas, submodel_id: str, path: str) -> Any:
    entry = aas.node_registry.get_value_node(submodel_id, path)
    return await entry.node.get_value()


async def aas_write(aas, submodel_id: str, path: str, value: Any) -> None:
    """Escreve no nó do AAS como uma extensão ou a API REST fariam."""
    entry = aas.node_registry.get_value_node(submodel_id, path)
    from faaster.parser.creators.base import resolve_variant_type
    await entry.node.set_value(value, resolve_variant_type(entry.value_type))

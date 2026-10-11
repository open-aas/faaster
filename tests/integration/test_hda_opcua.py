"""
HDA de ponta a ponta: modelo AAS com policies faaster:hda:* → address space
OPC UA → TimescaleDB, lido por um cliente OPC UA via HistoryRead.
"""
import asyncio
import json
from argparse import Namespace
from datetime import datetime, timedelta, timezone

import pytest
from asyncua import Client, ua

from faaster.asset_administration_shell import AssetAdministrationShell
from faaster.hda.manager import HDAManager
from faaster.hda.storage import _table_name
from faaster.infra.database_timescale import TimescaleDatabase
from faaster.interfaces.types import FaasterVariantType

from .conftest import _free_port


SUBMODEL_ID = "urn:faaster:test:sm:energy"


def hda(**extensions):
    return [
        {"name": f"faaster:hda:{name}", "valueType": "xs:string", "value": value}
        for name, value in extensions.items()
    ]


def variable(id_short, value_type="xs:double", extensions=None):
    element = {
        "modelType": "Property",
        "idShort": id_short,
        "category": "VARIABLE",
        "valueType": value_type,
        "value": "0",
    }
    if extensions:
        element["extensions"] = extensions
    return element


MODEL = {
    "assetAdministrationShells": [{
        "modelType": "AssetAdministrationShell",
        "id": "urn:faaster:test:aas:hda",
        "idShort": "HdaAAS",
        "assetInformation": {"assetKind": "Instance", "globalAssetId": "urn:faaster:test:asset:hda"},
        "submodels": [{"type": "ModelReference", "keys": [{"type": "Submodel", "value": SUBMODEL_ID}]}],
    }],
    "submodels": [{
        "modelType": "Submodel",
        "id": SUBMODEL_ID,
        "idShort": "Energy",
        "submodelElements": [
            variable("Voltage", extensions=hda(levels="1min,1hour")),
            variable("ActiveEnergy", extensions=hda(mode="aggregate", window="1min", function="sum")),
            variable("Counter", value_type="xs:long"),
        ],
    }],
    "conceptDescriptions": [],
}


@pytest.fixture
async def hda_server(tmp_path, timescale_db):
    model = tmp_path / "model.json"
    model.write_text(json.dumps(MODEL))

    aas = AssetAdministrationShell(Namespace(url_database=None))
    server = aas._opcua_server
    endpoint = f"opc.tcp://127.0.0.1:{_free_port()}/faaster"
    await server.init()
    server.set_endpoint(endpoint)
    await server.register_namespace("urn:faaster:server")
    aas.address_space.set_namespace("urn:faaster:server")
    historized = await aas.parser.parse(str(model))

    # mesma database do timescale_db, que a apaga no fim
    db = TimescaleDatabase(url=timescale_db._url, db_name=timescale_db._db_name)
    manager = HDAManager(server=aas.server, db=db, registry=aas.node_registry)
    await manager.init(historized)
    await server.start()

    try:
        yield aas, manager, db, endpoint
    finally:
        await manager.stop()
        await server.stop()


def value_node(aas, id_short):
    return aas.node_registry.get_by_path(f"Energy/{id_short}/Value").node


async def write_series(aas, id_short, series, variant_type):
    node = value_node(aas, id_short)
    # em rajada e começando pelo valor atual do nó (0): toda escrita é historizada
    for timestamp, value in series:
        await aas.address_space.set_value(node, value, variant_type, source_timestamp=timestamp)


async def wait_for(condition, timeout=10.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not await condition():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("timeout waiting for HDA")
        await asyncio.sleep(0.05)


def minutes_ago(minutes: float) -> datetime:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    return now - timedelta(minutes=minutes)


async def test_client_reads_raw_and_level_history(hda_server):
    aas, _, db, endpoint = hda_server
    start = minutes_ago(30)
    series = [(start + timedelta(seconds=10 * i), float(i)) for i in range(12)]  # 2 minutos
    await write_series(aas, "Voltage", series, FaasterVariantType.Double)

    voltage = aas.node_registry.get_by_path("Energy/Voltage/Value")

    async def stored():
        rows = await db.query(_table_name(voltage), start, None, 100)
        return len(rows) == len(series)

    await wait_for(stored)

    async with Client(endpoint) as client:
        raw = client.get_node(value_node(aas, "Voltage").raw.nodeid)
        history = await raw.read_raw_history(start, datetime.now(timezone.utc))
        assert [(dv.SourceTimestamp, dv.Value.Value) for dv in history] == series

        # cliente que manda só EndTime: do fim para trás
        latest = await raw.read_raw_history(None, datetime.now(timezone.utc), numvalues=2)
        assert [dv.Value.Value for dv in latest] == [11.0, 10.0]

        prop = await raw.get_parent()
        level = await prop.get_child(f"{raw.nodeid.NamespaceIndex}:Value@1min")

        assert (await level.read_attribute(ua.AttributeIds.Historizing)).Value.Value is True
        access = (await level.read_attribute(ua.AttributeIds.AccessLevel)).Value.Value
        assert access & ua.AccessLevel.HistoryRead.mask

        buckets = await level.read_raw_history(start, datetime.now(timezone.utc))
        assert [(dv.SourceTimestamp, dv.Value.Value) for dv in buckets] == [
            (start, 2.5),
            (start + timedelta(minutes=1), 8.5),
        ]


async def test_integer_history_keeps_its_type(hda_server):
    aas, _, db, endpoint = hda_server
    start = minutes_ago(10)
    await write_series(aas, "Counter", [(start, 41), (start + timedelta(seconds=1), 42)], FaasterVariantType.Int64)

    counter = aas.node_registry.get_by_path("Energy/Counter/Value")

    async def stored():
        return len(await db.query(_table_name(counter), start, None, 10)) == 2

    await wait_for(stored)

    async with Client(endpoint) as client:
        node = client.get_node(value_node(aas, "Counter").raw.nodeid)
        history = await node.read_raw_history(start, datetime.now(timezone.utc))

    assert [dv.Value for dv in history] == [ua.Variant(41, ua.VariantType.Int64), ua.Variant(42, ua.VariantType.Int64)]


async def test_aggregate_windows_are_readable_by_clients(hda_server):
    aas, manager, _, endpoint = hda_server
    start = minutes_ago(10)
    series = [
        (start + timedelta(seconds=5), 1.0),
        (start + timedelta(seconds=50), 2.0),
        (start + timedelta(minutes=1, seconds=30), 10.0),
    ]
    await write_series(aas, "ActiveEnergy", series, FaasterVariantType.Double)

    energy = aas.node_registry.get_by_path("Energy/ActiveEnergy/Value")

    async def buffered():
        return sum(len(samples) for samples in energy.buffer.buckets.values()) == len(series)

    await wait_for(buffered)
    await manager._storage.flush(energy, _table_name(energy))

    async with Client(endpoint) as client:
        node = client.get_node(value_node(aas, "ActiveEnergy").raw.nodeid)
        history = await node.read_raw_history(start, datetime.now(timezone.utc))

    assert [(dv.SourceTimestamp, dv.Value.Value) for dv in history] == [
        (start, 3.0),
        (start + timedelta(minutes=1), 10.0),
    ]

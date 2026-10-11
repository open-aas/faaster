"""AssetBinder ponta a ponta contra um CLP simulado (servidor OPC UA local)."""
import asyncio

from faaster.binding.binder import AssetBinder
from faaster.binding.drivers.base import IAssetDriver

from tests.binding.conftest import (
    AIMC_SEMANTIC, IO_SM, FakePlc, aas_value, aas_write, aid_path, build_model, io_path,
    mapping, wait_for,
)


async def test_north_asset_values_reach_the_aas(plc, faaster_with):
    aas, binder = await faaster_with(build_model(plc))
    await binder.start()

    # valor inicial chega pela subscription; Temp resolvido pelo NodeId do href
    await wait_for(lambda: _eq(aas, "Sensors.Temp", 20.0))

    await plc.set("xIn", True)
    await wait_for(lambda: _eq(aas, "Sensors.In", True))
    await plc.set("rTemp", 42.5)
    await wait_for(lambda: _eq(aas, "Sensors.Temp", 42.5))


async def test_south_aas_writes_reach_the_asset(plc, faaster_with):
    aas, binder = await faaster_with(build_model(plc))
    await binder.start()
    await wait_for(lambda: _eq(aas, "Sensors.Temp", 20.0))

    await aas_write(aas, IO_SM, "Actuators.Out", True)
    await wait_for(lambda: _plc_eq(plc, "xOut", True))
    # o eco do CLP mantém o AAS coerente, sem laço
    await asyncio.sleep(0.2)
    assert await aas_value(aas, IO_SM, "Actuators.Out") is True
    assert await plc.read("xOut") is True


async def test_south_pulse_is_not_lost(plc, faaster_with):
    """True e False em sequência rápida: o último comando prevalece no ativo."""
    aas, binder = await faaster_with(build_model(plc))
    await binder.start()
    await wait_for(lambda: _eq(aas, "Sensors.Temp", 20.0))

    await aas_write(aas, IO_SM, "Actuators.Out", True)
    await aas_write(aas, IO_SM, "Actuators.Out", False)
    await asyncio.sleep(0.3)
    assert await plc.read("xOut") is False
    assert await aas_value(aas, IO_SM, "Actuators.Out") is False


async def test_south_node_becomes_writable_for_opcua_clients(plc, faaster_with):
    from asyncua import ua

    aas, binder = await faaster_with(build_model(plc))
    await binder.start()
    out = aas.node_registry.get_value_node(IO_SM, "Actuators.Out").node.raw
    sensor = aas.node_registry.get_value_node(IO_SM, "Sensors.In").node.raw

    assert ua.AccessLevel.CurrentWrite in await out.get_access_level()
    assert ua.AccessLevel.CurrentWrite not in await sensor.get_access_level()


async def test_write_to_asset_owned_node_is_overwritten(plc, faaster_with):
    aas, binder = await faaster_with(build_model(plc))
    await binder.start()
    await wait_for(lambda: _eq(aas, "Sensors.Temp", 20.0))

    await aas_write(aas, IO_SM, "Sensors.In", True)   # sem mapeamento sul
    await asyncio.sleep(0.2)
    assert await plc.read("xIn") is False             # não vai para o ativo
    await plc.set("xIn", True)
    await plc.set("xIn", False)
    await wait_for(lambda: _eq(aas, "Sensors.In", False))


async def test_aid_without_aimc_binds_nothing(plc, faaster_with):
    aas, binder = await faaster_with(build_model(plc, with_aimc=False))
    assert binder.is_empty


async def test_aimc_1_x_is_ignored(plc, faaster_with):
    old = AIMC_SEMANTIC.replace("/2/0/", "/1/0/")
    aas, binder = await faaster_with(build_model(plc, aimc_semantic=old))
    assert binder.is_empty


async def test_mapping_with_transformation_is_skipped(plc, faaster_with):
    m = mapping([("xIn", aid_path("xIn"), io_path("Sensors", "In"))], transformation="function aimc_main(s) end")
    aas, binder = await faaster_with(build_model(plc, mappings=[m]))
    assert binder.is_empty


async def test_unpaired_ids_are_rejected(plc, faaster_with):
    m = mapping([("xIn", aid_path("xIn"), io_path("Sensors", "In"))])
    m["value"][1]["value"][0]["value"][1]["value"] = "other"   # SinkId diferente
    aas, binder = await faaster_with(build_model(plc, mappings=[m]))
    assert binder.is_empty


async def test_unknown_target_is_skipped(plc, faaster_with):
    m = mapping([
        ("xIn", aid_path("xIn"), io_path("Sensors", "Missing")),
        ("rTemp", aid_path("rTemp"), io_path("Sensors", "Temp")),
    ])
    aas, binder = await faaster_with(build_model(plc, mappings=[m]))
    assert list(binder._bindings.values())[0].north.keys() == {"rTemp"}


async def test_unreachable_asset_does_not_block_start(faaster_with):
    plc = FakePlc(url="opc.tcp://127.0.0.1:9", ns=2, nodes={})
    aas, binder = await faaster_with(build_model(plc))
    await asyncio.wait_for(binder.start(), timeout=15)
    driver = list(binder._bindings.values())[0].driver
    assert driver is not None and not driver.connected


async def test_reconnects_after_asset_restart(faaster_with, monkeypatch):
    """O CLP cai e volta: o driver reconecta e retoma a subscription."""
    from faaster.binding.drivers import opcua
    monkeypatch.setattr(opcua, "_RECONNECT_DELAY", 0.5)
    monkeypatch.setattr(opcua, "_WATCHDOG_INTERVAL", 0.2)
    from asyncua import Server, ua
    from tests.binding.conftest import free_port, PLC_NS

    port = free_port()
    url = f"opc.tcp://127.0.0.1:{port}"

    async def start_plc():
        server = Server()
        await server.init()
        server.set_endpoint(url)
        ns = await server.register_namespace(PLC_NS)
        ds = await server.nodes.objects.add_folder(ns, "DeviceSet")
        dev = await ds.add_object(ns, "plcTest")
        inputs = await dev.add_folder(ns, "Inputs")
        outputs = await dev.add_folder(ns, "Outputs")
        x_in = await inputs.add_variable(ns, "xIn", False, ua.VariantType.Boolean)
        await inputs.add_variable(ua.NodeId("plcTest.rTemp", ns), ua.QualifiedName("rTemp", ns), 20.0,
                                  ua.VariantType.Double)
        await outputs.add_variable(ns, "xOut", False, ua.VariantType.Boolean)
        await server.start()
        return server, ns, x_in

    server, ns, _ = await start_plc()
    aas, binder = await faaster_with(build_model(FakePlc(url=url, ns=ns, nodes={})))
    await binder.start()
    await wait_for(lambda: _eq(aas, "Sensors.Temp", 20.0))

    await server.stop()
    await asyncio.sleep(0.5)
    server, ns, x_in = await start_plc()
    try:
        await x_in.write_value(True)
        await wait_for(lambda: _eq(aas, "Sensors.In", True), timeout=10)
    finally:
        # o stop() do servidor espera as conexões fecharem: desconecta antes
        await binder.stop()
        await server.stop()


async def test_drivers_are_selected_by_scheme(plc, faaster_with):
    class FakeDriver(IAssetDriver):
        schemes = ["opc.tcp"]
        started = []

        async def start(self, observe, on_value, poll=None):
            FakeDriver.started.append(sorted(a.name for a in observe))
            self._on_value = on_value

        async def write(self, affordance, value):
            pass

        async def stop(self):
            pass

        @property
        def connected(self):
            return True

    aas, _ = await faaster_with(build_model(plc))
    binder = AssetBinder(aas.address_space, aas.node_registry, drivers={"opc.tcp": FakeDriver})
    binder.configure(aas.parser.document)
    await binder.start()
    assert FakeDriver.started == [["rTemp", "xIn", "xOut"]]
    await binder.stop()


async def _eq(aas, path, expected):
    return await aas_value(aas, IO_SM, path) == expected


async def _plc_eq(plc, name, expected):
    return await plc.read(name) == expected

"""
Objeto FaasterRuntime no espaço de endereços (decisão D16): saúde e métricas do runtime
expostas como nós OPC UA, lidas pelo agente do FTM na mesma sessão da verificação de saúde.
"""
from datetime import datetime, timezone

from faaster.infra.runtime_info import RUNTIME_OBJECT, publish_runtime_info


async def _child_value(obj, name):
    node = await obj.raw.get_child([f"{obj.raw.nodeid.NamespaceIndex}:{name}"])
    return await node.read_value()


async def test_runtime_object_exposes_version_extensions_and_errors(address_space, objects_node):
    before = datetime.now(timezone.utc)

    obj = await publish_runtime_info(
        address_space,
        version="1.0.0a3",
        loaded=["Energy", "Nameplate"],
        failed={"Maintenance": "import_error: ModuleNotFoundError"},
    )

    names = [(await c.raw.read_browse_name()).Name for c in await objects_node.get_children()]
    assert RUNTIME_OBJECT in names
    assert await _child_value(obj, "Version") == "1.0.0a3"
    assert await _child_value(obj, "ExtensionsLoaded") == ["Energy", "Nameplate"]
    assert await _child_value(obj, "ExtensionsFailed") == [
        "Maintenance: import_error: ModuleNotFoundError"
    ]
    assert await _child_value(obj, "ExtensionErrors") == 1
    started = await _child_value(obj, "StartedAt")
    started = started if started.tzinfo else started.replace(tzinfo=timezone.utc)
    assert started >= before.replace(microsecond=0)


async def test_runtime_object_without_extensions(address_space, objects_node):
    obj = await publish_runtime_info(address_space, version="x", loaded=[], failed={})

    assert await _child_value(obj, "ExtensionsLoaded") == []
    assert await _child_value(obj, "ExtensionErrors") == 0

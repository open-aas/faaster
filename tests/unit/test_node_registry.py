import pytest
from unittest.mock import MagicMock
from faaster.parser.node_registry import NodeRegistry, NodeMetadata, OperationEntry
from faaster.extensions.method_binder import MethodBinder
from faaster.interfaces.types import FaasterVariantType


def _make_node(node_id: str):
    node = MagicMock()
    node.node_id = node_id
    return node


def _make_metadata(node_id="ns=1;i=100", path="Sub/Prop/Value", id_short="Prop",
                   submodel="Sub", submodel_id="urn:sub"):
    return NodeMetadata(
        node=_make_node(node_id),
        path=path,
        id_short=id_short,
        submodel=submodel,
        submodel_id=submodel_id,
        variant_type=FaasterVariantType.Float,
    )


def test_register_and_get_by_node_id():
    registry = NodeRegistry()
    meta = _make_metadata()
    registry.register(meta)
    found = registry.get_by_node_id("ns=1;i=100")
    assert found is meta


def test_get_by_path():
    registry = NodeRegistry()
    meta = _make_metadata()
    registry.register(meta)
    found = registry.get_by_path("Sub/Prop/Value")
    assert found is meta


def test_get_by_semantic_id():
    registry = NodeRegistry()
    meta = _make_metadata()
    meta.semantic_id = "urn:iec61360:voltage"
    registry.register(meta)
    found = registry.get_by_semantic_id("urn:iec61360:voltage")
    assert found is meta


def test_get_by_node_id_missing_returns_none():
    registry = NodeRegistry()
    assert registry.get_by_node_id("ns=99;i=999") is None


def test_get_by_path_missing_returns_none():
    registry = NodeRegistry()
    assert registry.get_by_path("Missing/Path") is None


def test_get_by_submodel():
    registry = NodeRegistry()
    meta1 = _make_metadata("ns=1;i=1", "Sub/A/Value", "A")
    meta2 = _make_metadata("ns=1;i=2", "Sub/B/Value", "B")
    registry.register(meta1)
    registry.register(meta2)
    result = registry.get_by_submodel("Sub")
    assert len(result) == 2


def test_resolve_priority_node_id_first():
    registry = NodeRegistry()
    meta = _make_metadata()
    meta.semantic_id = "urn:sem"
    registry.register(meta)
    found = registry.resolve(node_id="ns=1;i=100", semantic_id="urn:sem")
    assert found is meta


def test_all_returns_all_registered():
    registry = NodeRegistry()
    registry.register(_make_metadata("ns=1;i=1", "Sub/A/Value", "A"))
    registry.register(_make_metadata("ns=1;i=2", "Sub/B/Value", "B"))
    assert len(registry.all) == 2


def test_set_and_get_aas_id_short():
    registry = NodeRegistry()
    registry.set_aas_id_short("MyAAS")
    assert registry.aas_id_short == "MyAAS"


def test_register_submodel_node_and_node_submodels():
    registry = NodeRegistry()
    node = _make_node("ns=1;i=10")
    registry.register_submodel_node("MySub", node)
    assert "MySub" in registry.node_submodels
    assert registry.node_submodels["MySub"] is node


def test_register_operation_and_get_operations():
    registry = NodeRegistry()
    binder = MethodBinder()
    node = _make_node("ns=1;i=50")
    registry.register_operation("MySub", "StartProcess", node, binder)

    ops = registry.get_operations("MySub")
    assert len(ops) == 1
    assert ops[0].id_short == "StartProcess"
    assert ops[0].binder is binder


def test_get_operations_unknown_submodel_returns_empty():
    registry = NodeRegistry()
    assert registry.get_operations("Unknown") == []


def test_register_multiple_operations_same_submodel():
    registry = NodeRegistry()
    for name in ("Start", "Stop", "Reset"):
        registry.register_operation("Ctrl", name, _make_node(f"ns=1;i={ord(name[0])}"), MethodBinder())
    assert len(registry.get_operations("Ctrl")) == 3

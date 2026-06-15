"""
Testes de integração da cadeia completa: OperationCreator → MethodBinder → uamethod.

Usa asyncua.Server in-memory para verificar que:
    1. OperationCreator cria o nó método no address space real
    2. O nó criado tem NodeId válido
    3. O MethodBinder delega corretamente ao handler após bind()
    4. uamethod converte os tipos OPC UA → Python antes de chamar o handler
    5. Operações independentes têm Binders independentes
"""
import pytest
from unittest.mock import MagicMock
from asyncua.common.methods import uamethod

from faaster.infra.address_space import NodeAdapter
from faaster.parser.creators.operation_creator import OperationCreator
from faaster.extensions.method_binder import MethodBinder
from faaster.interfaces.types import FaasterVariantType


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _op_element(id_short="StartProcess", input_vars=None, output_vars=None):
    el = MagicMock()
    el.id_short = id_short
    el.modelType = "Operation"
    el.inputVariables = input_vars or []
    el.outputVariables = output_vars or []
    return el


def _var(id_short, value_type="xs:float"):
    v = MagicMock()
    v.value = MagicMock()
    v.value.id_short = id_short
    v.value.valueType = value_type
    return v


# ------------------------------------------------------------------
# Criação de nós método no address space real
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_method_node_returns_node_adapter(address_space, objects_node):
    creator = OperationCreator()
    method_node, _ = await creator.create(objects_node, _op_element(), address_space)
    assert isinstance(method_node, NodeAdapter)


@pytest.mark.asyncio
async def test_created_method_node_has_valid_node_id(address_space, objects_node):
    creator = OperationCreator()
    method_node, _ = await creator.create(objects_node, _op_element("Calibrate"), address_space)
    # asyncua serializa como "NodeId(Identifier=X, NamespaceIndex=Y, ...)"
    assert method_node.raw.nodeid.NamespaceIndex != 0
    assert len(method_node.node_id) > 0


@pytest.mark.asyncio
async def test_create_returns_unbound_binder(address_space, objects_node):
    creator = OperationCreator()
    _, binder = await creator.create(objects_node, _op_element(), address_space)
    assert isinstance(binder, MethodBinder)
    assert binder.is_bound is False


@pytest.mark.asyncio
async def test_operation_container_node_is_created(address_space, objects_node):
    """OperationCreator cria um nó Object container antes do Method."""
    creator = OperationCreator()
    before = await objects_node.get_children()
    await creator.create(objects_node, _op_element("MyOp"), address_space)
    after = await objects_node.get_children()
    assert len(after) > len(before)


@pytest.mark.asyncio
async def test_two_operations_have_different_node_ids(address_space, objects_node):
    creator = OperationCreator()
    node1, _ = await creator.create(objects_node, _op_element("Op1"), address_space)
    node2, _ = await creator.create(objects_node, _op_element("Op2"), address_space)
    assert node1.node_id != node2.node_id


@pytest.mark.asyncio
async def test_two_operations_have_independent_binders(address_space, objects_node):
    creator = OperationCreator()
    _, binder1 = await creator.create(objects_node, _op_element("A"), address_space)
    _, binder2 = await creator.create(objects_node, _op_element("B"), address_space)

    async def handler_a(parent): return ["a"]
    binder1.bind(handler_a)

    assert binder1.is_bound is True
    assert binder2.is_bound is False


@pytest.mark.asyncio
async def test_method_with_input_args_created(address_space, objects_node):
    """Operação com inputVariables cria nó método sem erro."""
    creator = OperationCreator()
    inputs = [_var("setpoint", "xs:float"), _var("mode", "xs:string")]
    method_node, _ = await creator.create(
        objects_node,
        _op_element("Configure", input_vars=inputs),
        address_space,
    )
    assert isinstance(method_node, NodeAdapter)


@pytest.mark.asyncio
async def test_method_with_output_args_created(address_space, objects_node):
    creator = OperationCreator()
    outputs = [_var("result", "xs:boolean")]
    method_node, _ = await creator.create(
        objects_node,
        _op_element("Check", output_vars=outputs),
        address_space,
    )
    assert isinstance(method_node, NodeAdapter)


# ------------------------------------------------------------------
# MethodBinder + uamethod com nó real
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_binder_without_args_returns_result(address_space, objects_node):
    creator = OperationCreator()
    _, binder = await creator.create(objects_node, _op_element("NoArgs"), address_space)

    async def handler(parent):
        # None → _format_call_outputs retorna []
        return None

    binder.bind(uamethod(handler))
    assert binder.is_bound is True
    # uamethod espera ua.NodeId como primeiro arg, não asyncua.Node
    result = await binder(objects_node.raw.nodeid)
    assert result == []


@pytest.mark.asyncio
async def test_binder_handler_receives_call(address_space, objects_node):
    creator = OperationCreator()
    _, binder = await creator.create(objects_node, _op_element("Echo"), address_space)

    invocations = []

    async def handler(parent):
        invocations.append(True)
        return None

    binder.bind(uamethod(handler))
    await binder(objects_node.raw.nodeid)
    assert invocations == [True]


@pytest.mark.asyncio
async def test_binder_can_be_rebound(address_space, objects_node):
    creator = OperationCreator()
    _, binder = await creator.create(objects_node, _op_element("Rebind"), address_space)

    calls = []

    async def v1(parent): calls.append("v1")
    async def v2(parent): calls.append("v2")

    binder.bind(uamethod(v1))
    await binder(objects_node.raw.nodeid)

    binder.bind(uamethod(v2))
    await binder(objects_node.raw.nodeid)

    # Apenas v2 deve ter sido chamada na segunda invocação
    assert calls == ["v1", "v2"]


@pytest.mark.asyncio
async def test_unbound_binder_returns_empty_on_real_node(address_space, objects_node):
    creator = OperationCreator()
    _, binder = await creator.create(objects_node, _op_element("Unbound"), address_space)

    assert binder.is_bound is False
    result = await binder(objects_node.raw.nodeid)
    assert result == []


# ------------------------------------------------------------------
# Integração com NodeRegistry
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_operation_node_can_be_registered(address_space, objects_node):
    """Verifica o fluxo completo: create → register → get_operations."""
    from faaster.parser.node_registry import NodeRegistry

    creator = OperationCreator()
    registry = NodeRegistry()

    method_node, binder = await creator.create(
        objects_node, _op_element("Process"), address_space
    )
    registry.register_operation("MySub", "Process", method_node, binder)

    ops = registry.get_operations("MySub")
    assert len(ops) == 1
    assert ops[0].id_short == "Process"
    assert ops[0].binder is binder
    assert ops[0].method_node is method_node


@pytest.mark.asyncio
async def test_multiple_operations_registered_and_bound(address_space, objects_node):
    from faaster.parser.node_registry import NodeRegistry
    from faaster.extensions.loader import _to_snake_case
    from types import SimpleNamespace

    creator = OperationCreator()
    registry = NodeRegistry()

    for name in ("Start", "Stop", "GetStatus"):
        node, binder = await creator.create(objects_node, _op_element(name), address_space)
        registry.register_operation("Ctrl", name, node, binder)

    # Simula bind_operations
    async def start(parent): return []
    async def stop(parent): return []
    async def get_status(parent): return []

    instance = SimpleNamespace(
        start=start,
        stop=stop,
        get_status=get_status,
    )

    for op in registry.get_operations("Ctrl"):
        method_name = _to_snake_case(op.id_short)
        handler = getattr(instance, method_name, None)
        if handler and callable(handler):
            op.binder.bind(uamethod(handler))

    ops = registry.get_operations("Ctrl")
    assert all(op.binder.is_bound for op in ops)

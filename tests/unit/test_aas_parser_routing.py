"""
Testes do AASParser focando no roteamento de elementos e rastreamento de path.

Não testa o parsing de arquivo (LoaderFactory) — apenas a lógica de
despacho de elementos e o registro correto no NodeRegistry.

Dependências mockadas:
    - IAddressSpace
    - IElementCreator (create_operation, create_property, etc.)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from faaster.parser.aas_parser import AASParser
from faaster.parser.node_registry import NodeRegistry
from faaster.extensions.method_binder import MethodBinder


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_address_space():
    as_ = AsyncMock()
    as_.add_folder.return_value = MagicMock(node_id="ns=1;i=1")
    as_.get_objects_node.return_value = AsyncMock(return_value=MagicMock())
    return as_


def _make_creator(method_node=None, binder=None):
    """IElementCreator com create_operation mockado."""
    m_node = method_node or MagicMock(node_id="ns=1;i=99")
    b = binder or MethodBinder()
    creator = AsyncMock()
    creator.create_operation.return_value = (m_node, b)
    creator.create_property.return_value = MagicMock(node_id="ns=1;i=50")
    creator.create_submodel_element_collection.return_value = MagicMock(node_id="ns=1;i=20")
    return creator, m_node, b


def _operation_element(id_short="StartProcess"):
    el = MagicMock()
    el.type_model = "Operation"
    el.id_short = id_short
    el.model_dump.return_value = {
        "id_short": id_short,
        "modelType": "Operation",
        "input_variables": [],
        "output_variables": [],
        "inoutput_variables": [],
    }
    return el


def _property_element(id_short="Voltage", category="VARIABLE"):
    el = MagicMock()
    el.type_model = "Property"
    el.id_short = id_short
    el.category = category
    el.semantic_id = None
    el.value_type = "xs:float"
    el.extensions = []
    return el


def _collection_element(id_short="MyCollection", children=None):
    el = MagicMock()
    el.type_model = "SubmodelElementCollection"
    el.id_short = id_short
    el.model_dump.return_value = {"id_short": id_short, "modelType": "SubmodelElementCollection", "value": None}
    el.value = children or []
    return el


# ------------------------------------------------------------------
# Testes de _parse_operation
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_operation_registers_in_registry():
    registry = NodeRegistry()
    creator, m_node, binder = _make_creator()
    parser = AASParser(
        address_space=_make_address_space(),
        creator=creator,
        node_registry=registry,
    )
    parent = MagicMock()
    element = _operation_element("StartProcess")

    with patch("faaster.parser.aas_parser.Operation") as MockOp:
        mock_op = MagicMock()
        mock_op.id_short = "StartProcess"
        MockOp.return_value = mock_op
        await parser._parse_operation(parent, element, "MySub")

    ops = registry.get_operations("MySub")
    assert len(ops) == 1
    assert ops[0].id_short == "StartProcess"
    assert ops[0].binder is binder


@pytest.mark.asyncio
async def test_parse_operation_does_not_register_when_method_node_is_none():
    registry = NodeRegistry()
    creator = AsyncMock()
    creator.create_operation.return_value = (None, MethodBinder())
    parser = AASParser(
        address_space=_make_address_space(),
        creator=creator,
        node_registry=registry,
    )

    with patch("faaster.parser.aas_parser.Operation") as MockOp:
        mock_op = MagicMock()
        mock_op.id_short = "StartProcess"
        MockOp.return_value = mock_op
        await parser._parse_operation(MagicMock(), _operation_element(), "Sub")

    assert registry.get_operations("Sub") == []


@pytest.mark.asyncio
async def test_parse_operation_does_not_register_when_id_short_is_none():
    registry = NodeRegistry()
    creator, m_node, binder = _make_creator()
    parser = AASParser(
        address_space=_make_address_space(),
        creator=creator,
        node_registry=registry,
    )

    with patch("faaster.parser.aas_parser.Operation") as MockOp:
        mock_op = MagicMock()
        mock_op.id_short = None
        MockOp.return_value = mock_op
        await parser._parse_operation(MagicMock(), _operation_element(), "Sub")

    assert registry.get_operations("Sub") == []


@pytest.mark.asyncio
async def test_parse_operation_calls_create_operation():
    registry = NodeRegistry()
    creator, _, _ = _make_creator()
    as_ = _make_address_space()
    parser = AASParser(address_space=as_, creator=creator, node_registry=registry)
    parent = MagicMock()

    with patch("faaster.parser.aas_parser.Operation") as MockOp:
        MockOp.return_value = MagicMock(id_short="Calibrate")
        await parser._parse_operation(parent, _operation_element("Calibrate"), "Sub")

    creator.create_operation.assert_called_once()


# ------------------------------------------------------------------
# Testes de roteamento em _parse_submodel_element
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_routes_operation_to_parse_operation():
    registry = NodeRegistry()
    creator, _, _ = _make_creator()
    parser = AASParser(
        address_space=_make_address_space(),
        creator=creator,
        node_registry=registry,
    )

    with patch.object(parser, "_parse_operation", new=AsyncMock()) as mock_op:
        element = _operation_element()
        await parser._parse_submodel_element(
            parent=MagicMock(),
            element=element,
            submodel_id="urn:sub",
            current_path="MySub",
        )
        mock_op.assert_called_once()


@pytest.mark.asyncio
async def test_routes_property_to_parse_data_element():
    registry = NodeRegistry()
    creator, _, _ = _make_creator()
    parser = AASParser(
        address_space=_make_address_space(),
        creator=creator,
        node_registry=registry,
    )

    with patch.object(parser, "_parse_data_element", new=AsyncMock()) as mock_de:
        await parser._parse_submodel_element(
            parent=MagicMock(),
            element=_property_element(),
            submodel_id="urn:sub",
            current_path="MySub",
        )
        mock_de.assert_called_once()


@pytest.mark.asyncio
async def test_routes_collection_to_parse_collection():
    registry = NodeRegistry()
    creator, _, _ = _make_creator()
    parser = AASParser(
        address_space=_make_address_space(),
        creator=creator,
        node_registry=registry,
    )

    with patch.object(parser, "_parse_collection", new=AsyncMock()) as mock_col:
        await parser._parse_submodel_element(
            parent=MagicMock(),
            element=_collection_element(),
            submodel_id="urn:sub",
            current_path="MySub",
        )
        mock_col.assert_called_once()


# ------------------------------------------------------------------
# Rastreamento de submodel_id_short via current_path
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submodel_id_short_extracted_from_path_root():
    """'MySub' → submodel_id_short = 'MySub'"""
    registry = NodeRegistry()
    creator, _, _ = _make_creator()
    parser = AASParser(
        address_space=_make_address_space(),
        creator=creator,
        node_registry=registry,
    )

    with patch.object(parser, "_parse_operation", new=AsyncMock()) as mock_op:
        await parser._parse_submodel_element(
            parent=MagicMock(),
            element=_operation_element(),
            submodel_id="urn:sub",
            current_path="ElectricData",
        )
        _, kwargs = mock_op.call_args
        assert kwargs.get("submodel_id_short") == "ElectricData" or mock_op.call_args[0][2] == "ElectricData"


@pytest.mark.asyncio
async def test_submodel_id_short_extracted_from_nested_path():
    """'ElectricData/Sensors/Status' → submodel_id_short = 'ElectricData'"""
    registry = NodeRegistry()
    creator, _, _ = _make_creator()
    parser = AASParser(
        address_space=_make_address_space(),
        creator=creator,
        node_registry=registry,
    )

    captured = {}

    async def capture(parent, element, submodel_id_short):
        captured["id_short"] = submodel_id_short

    with patch.object(parser, "_parse_operation", new=capture):
        await parser._parse_submodel_element(
            parent=MagicMock(),
            element=_operation_element(),
            submodel_id="urn:sub",
            current_path="ElectricData/Sensors/Status",
        )

    assert captured["id_short"] == "ElectricData"


@pytest.mark.asyncio
async def test_multiple_operations_same_submodel_all_registered():
    registry = NodeRegistry()
    creator = AsyncMock()
    nodes_binders = [
        (MagicMock(node_id=f"ns=1;i={i}"), MethodBinder())
        for i in range(3)
    ]
    creator.create_operation.side_effect = nodes_binders

    parser = AASParser(
        address_space=_make_address_space(),
        creator=creator,
        node_registry=registry,
    )

    op_names = ["Start", "Stop", "Reset"]

    for name in op_names:
        with patch("faaster.parser.aas_parser.Operation") as MockOp:
            MockOp.return_value = MagicMock(id_short=name)
            await parser._parse_operation(MagicMock(), _operation_element(name), "Ctrl")

    ops = registry.get_operations("Ctrl")
    assert len(ops) == 3
    assert {op.id_short for op in ops} == {"Start", "Stop", "Reset"}

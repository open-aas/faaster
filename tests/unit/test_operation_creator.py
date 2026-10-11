"""
Testes do OperationCreator com IAddressSpace mockado.

Foco:
    - Retorna (method_node, MethodBinder) para qualquer operação
    - MethodBinder começa não vinculado
    - add_object / add_property / add_method chamados com args corretos
    - MethodArguments gerados a partir dos inputVariables / outputVariables

Assinatura do método:  create(self, parent, element, address_space)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, call

from faaster.parser.creators.operation_creator import OperationCreator
from faaster.extensions.method_binder import MethodBinder
from faaster.aas_metamodel.models.operation import Operation
from faaster.aas_metamodel.models.operation_variable import OperationVariable


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_address_space():
    """IAddressSpace com todos os métodos async mockados."""
    as_ = AsyncMock()
    as_.add_object.return_value = MagicMock(node_id="ns=1;i=10")
    as_.add_property.return_value = MagicMock(node_id="ns=1;i=11")
    as_.add_method.return_value = MagicMock(node_id="ns=1;i=12")
    return as_


def _make_element(
    id_short="StartProcess",
    model_type="Operation",
    input_vars=None,
    output_vars=None,
):
    """Operation real do metamodelo — stubs escondiam nomes de atributo errados."""
    return Operation(
        idShort=id_short,
        inputVariables=input_vars or None,
        outputVariables=output_vars or None,
    )


def _make_var(id_short="temperature", value_type="xs:float"):
    """OperationVariable serializada, como no JSON do AAS."""
    return {"value": {"modelType": "Property", "idShort": id_short, "valueType": value_type}}


# ------------------------------------------------------------------
# Testes
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returns_tuple_method_node_and_binder():
    creator = OperationCreator()
    as_ = _make_address_space()
    parent = MagicMock()

    method_node, binder = await creator.create(parent, _make_element(), as_)

    assert method_node is as_.add_method.return_value
    assert isinstance(binder, MethodBinder)


@pytest.mark.asyncio
async def test_binder_is_unbound_after_creation():
    creator = OperationCreator()
    as_ = _make_address_space()

    _, binder = await creator.create(MagicMock(), _make_element(), as_)

    assert binder.is_bound is False


@pytest.mark.asyncio
async def test_add_object_called_with_operation_name():
    creator = OperationCreator()
    as_ = _make_address_space()
    parent = MagicMock()

    await creator.create(parent, _make_element(id_short="Calibrate"), as_)

    as_.add_object.assert_called_once_with(parent, "Calibrate")


@pytest.mark.asyncio
async def test_properties_registered_on_op_node():
    creator = OperationCreator()
    as_ = _make_address_space()

    await creator.create(MagicMock(), _make_element(id_short="Run", model_type="Operation"), as_)

    calls = {c.args[1]: c.args[2] for c in as_.add_property.call_args_list}
    assert calls.get("IdShort") == "Run"
    assert calls.get("ModelType") == "Operation"


@pytest.mark.asyncio
async def test_add_method_called_with_binder_as_callback():
    creator = OperationCreator()
    as_ = _make_address_space()

    await creator.create(MagicMock(), _make_element(), as_)

    kwargs = as_.add_method.call_args.kwargs
    assert "callback" in kwargs
    assert isinstance(kwargs["callback"], MethodBinder)


@pytest.mark.asyncio
async def test_no_variables_passes_empty_args():
    creator = OperationCreator()
    as_ = _make_address_space()

    await creator.create(MagicMock(), _make_element(input_vars=[], output_vars=[]), as_)

    kwargs = as_.add_method.call_args.kwargs
    assert kwargs["input_args"] == []
    assert kwargs["output_args"] == []


@pytest.mark.asyncio
async def test_input_variables_build_method_arguments():
    creator = OperationCreator()
    as_ = _make_address_space()
    var = _make_var("temperature", "xs:float")

    await creator.create(MagicMock(), _make_element(input_vars=[var]), as_)

    kwargs = as_.add_method.call_args.kwargs
    assert len(kwargs["input_args"]) == 1
    assert kwargs["input_args"][0].name == "temperature"


@pytest.mark.asyncio
async def test_output_variables_build_method_arguments():
    creator = OperationCreator()
    as_ = _make_address_space()
    var = _make_var("result", "xs:boolean")

    await creator.create(MagicMock(), _make_element(output_vars=[var]), as_)

    kwargs = as_.add_method.call_args.kwargs
    assert len(kwargs["output_args"]) == 1
    assert kwargs["output_args"][0].name == "result"


@pytest.mark.asyncio
async def test_var_without_value_skipped():
    creator = OperationCreator()
    as_ = _make_address_space()

    # o metamodelo exige value; model_construct monta o caso defensivo sem validar
    empty_var = OperationVariable.model_construct(value=None)
    element = Operation.model_construct(id_short="Op", input_variables=[empty_var], output_variables=[])

    await creator.create(MagicMock(), element, as_)

    kwargs = as_.add_method.call_args.kwargs
    assert kwargs["input_args"] == []


@pytest.mark.asyncio
async def test_fallback_name_when_id_short_is_none():
    creator = OperationCreator()
    as_ = _make_address_space()
    parent = MagicMock()

    element = Operation.model_construct(id_short=None, input_variables=[], output_variables=[])
    await creator.create(parent, element, as_)

    as_.add_object.assert_called_once_with(parent, "Operation")


@pytest.mark.asyncio
async def test_binder_can_be_bound_after_creation():
    creator = OperationCreator()
    as_ = _make_address_space()

    _, binder = await creator.create(MagicMock(), _make_element(), as_)

    async def my_handler(parent): return [42]
    binder.bind(my_handler)
    assert binder.is_bound is True


@pytest.mark.asyncio
async def test_multiple_input_output_args():
    creator = OperationCreator()
    as_ = _make_address_space()
    inputs = [_make_var("a", "xs:float"), _make_var("b", "xs:string")]
    outputs = [_make_var("ok", "xs:boolean")]

    await creator.create(MagicMock(), _make_element(input_vars=inputs, output_vars=outputs), as_)

    kwargs = as_.add_method.call_args.kwargs
    assert len(kwargs["input_args"]) == 2
    assert len(kwargs["output_args"]) == 1
    assert kwargs["input_args"][0].name == "a"
    assert kwargs["input_args"][1].name == "b"

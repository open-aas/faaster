"""
Testes de ExtensionLoader._bind_operations() com NodeRegistry real.

Foco:
    - Métodos com nome snake_case correspondente ao IdShort são vinculados
    - Métodos sem correspondência ficam não vinculados
    - Conversão PascalCase → snake_case correta
    - uamethod é aplicado (binder.is_bound passa a True)
    - Submódulo sem operações → sem efeito
"""
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from faaster.extensions.loader import ExtensionLoader, _to_snake_case
from faaster.extensions.method_binder import MethodBinder
from faaster.parser.node_registry import NodeRegistry, OperationEntry


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_registry_with_ops(*id_shorts, submodel="MySub") -> NodeRegistry:
    """Cria um NodeRegistry com operações registradas."""
    registry = NodeRegistry()
    for name in id_shorts:
        binder = MethodBinder()
        node = MagicMock(node_id=f"ns=1;i={hash(name) % 1000}")
        registry.register_operation(
            submodel_id_short=submodel,
            id_short=name,
            method_node=node,
            binder=binder,
        )
    return registry


def _make_instance(**methods) -> SimpleNamespace:
    """
    Cria um stub de instância de extensão com exatamente os métodos definidos.
    Usa SimpleNamespace para que atributos não definidos retornem None via getattr(..., None),
    evitando que MagicMock auto-gere callables para qualquer nome.
    """
    return SimpleNamespace(**methods)


def _make_loader(registry: NodeRegistry) -> ExtensionLoader:
    return ExtensionLoader(
        address_space=AsyncMock(),
        registry=registry,
    )


# ------------------------------------------------------------------
# Testes de _to_snake_case (helper interno)
# ------------------------------------------------------------------

def test_to_snake_case_simple():
    assert _to_snake_case("StartProcess") == "start_process"


def test_to_snake_case_already_lower():
    assert _to_snake_case("calibrate") == "calibrate"


def test_to_snake_case_three_words():
    assert _to_snake_case("GetTemperatureValue") == "get_temperature_value"


def test_to_snake_case_single_word():
    assert _to_snake_case("Run") == "run"


# ------------------------------------------------------------------
# Testes de _bind_operations
# ------------------------------------------------------------------

def test_bind_operations_matching_method():
    registry = _make_registry_with_ops("StartProcess")
    loader = _make_loader(registry)

    async def start_process(parent): return []

    instance = _make_instance(start_process=start_process)

    with patch("faaster.extensions.loader.uamethod", side_effect=lambda f: f):
        loader._bind_operations("MySub", instance)

    ops = registry.get_operations("MySub")
    assert ops[0].binder.is_bound is True


def test_bind_operations_non_matching_stays_unbound():
    registry = _make_registry_with_ops("StartProcess")
    loader = _make_loader(registry)

    # Instância não tem o método correspondente
    instance = SimpleNamespace()

    with patch("faaster.extensions.loader.uamethod", side_effect=lambda f: f):
        loader._bind_operations("MySub", instance)

    ops = registry.get_operations("MySub")
    assert ops[0].binder.is_bound is False


def test_bind_operations_partial_binding():
    registry = _make_registry_with_ops("Start", "Stop", "Reset", submodel="Ctrl")
    loader = _make_loader(registry)

    async def start(parent): return []
    async def stop(parent): return []

    instance = _make_instance(start=start, stop=stop)  # reset ausente

    with patch("faaster.extensions.loader.uamethod", side_effect=lambda f: f):
        loader._bind_operations("Ctrl", instance)

    ops = {op.id_short: op for op in registry.get_operations("Ctrl")}
    assert ops["Start"].binder.is_bound is True
    assert ops["Stop"].binder.is_bound is True
    assert ops["Reset"].binder.is_bound is False


def test_bind_operations_no_ops_for_submodel():
    registry = NodeRegistry()
    loader = _make_loader(registry)

    instance = MagicMock()

    # Não deve levantar exceção
    loader._bind_operations("Unknown", instance)


def test_bind_operations_empty_registry():
    registry = NodeRegistry()
    loader = _make_loader(registry)

    loader._bind_operations("AnySubmodel", MagicMock())  # sem ops


def test_bind_operations_uamethod_applied():
    """Verifica que uamethod é chamado com o handler (não o handler bruto)."""
    registry = _make_registry_with_ops("Run")
    loader = _make_loader(registry)

    async def run(parent): return []
    instance = _make_instance(run=run)

    applied = []

    def fake_uamethod(fn):
        applied.append(fn)
        return fn

    with patch("faaster.extensions.loader.uamethod", side_effect=fake_uamethod):
        loader._bind_operations("MySub", instance)

    assert len(applied) == 1
    assert applied[0] is run


def test_bind_operations_multi_word_pascal_case():
    """GetTemperatureValue → get_temperature_value deve ser vinculado."""
    registry = _make_registry_with_ops("GetTemperatureValue")
    loader = _make_loader(registry)

    async def get_temperature_value(parent): return []
    instance = _make_instance(get_temperature_value=get_temperature_value)

    with patch("faaster.extensions.loader.uamethod", side_effect=lambda f: f):
        loader._bind_operations("MySub", instance)

    ops = registry.get_operations("MySub")
    assert ops[0].binder.is_bound is True


def test_bind_operations_non_callable_attribute_skipped():
    """Atributo com mesmo nome mas não callable → deve ficar não vinculado."""
    registry = _make_registry_with_ops("Run")
    loader = _make_loader(registry)

    instance = SimpleNamespace(run="not a function")  # string, não callable

    with patch("faaster.extensions.loader.uamethod", side_effect=lambda f: f):
        loader._bind_operations("MySub", instance)

    ops = registry.get_operations("MySub")
    assert ops[0].binder.is_bound is False


def test_bind_operations_multiple_submodels_isolated():
    """Operações de submodelos diferentes não interferem entre si."""
    registry = _make_registry_with_ops("Start", submodel="SubA")
    registry.register_operation(
        submodel_id_short="SubB",
        id_short="Run",
        method_node=MagicMock(node_id="ns=1;i=200"),
        binder=MethodBinder(),
    )
    loader = _make_loader(registry)

    async def start(parent): return []
    instance_a = _make_instance(start=start)

    with patch("faaster.extensions.loader.uamethod", side_effect=lambda f: f):
        loader._bind_operations("SubA", instance_a)

    # SubA vinculado, SubB intacto
    assert registry.get_operations("SubA")[0].binder.is_bound is True
    assert registry.get_operations("SubB")[0].binder.is_bound is False

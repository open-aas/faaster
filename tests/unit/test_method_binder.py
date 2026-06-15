import pytest
from faaster.extensions.method_binder import MethodBinder


@pytest.mark.asyncio
async def test_unbound_returns_empty_list():
    binder = MethodBinder()
    result = await binder(parent=object())
    assert result == []


@pytest.mark.asyncio
async def test_is_bound_false_initially():
    binder = MethodBinder()
    assert binder.is_bound is False


@pytest.mark.asyncio
async def test_bind_sets_handler():
    binder = MethodBinder()

    async def handler(parent):
        return [42]

    binder.bind(handler)
    assert binder.is_bound is True


@pytest.mark.asyncio
async def test_bound_handler_is_called():
    binder = MethodBinder()
    calls = []

    async def handler(parent, *args):
        calls.append(args)
        return [99]

    binder.bind(handler)
    result = await binder(object(), 1, 2)
    assert result == [99]
    assert calls == [(1, 2)]


@pytest.mark.asyncio
async def test_bind_can_be_replaced():
    binder = MethodBinder()

    async def first(parent): return ["first"]
    async def second(parent): return ["second"]

    binder.bind(first)
    binder.bind(second)

    result = await binder(parent=object())
    assert result == ["second"]


@pytest.mark.asyncio
async def test_unbound_ignores_extra_args():
    binder = MethodBinder()
    result = await binder(object(), "a", "b", 123)
    assert result == []

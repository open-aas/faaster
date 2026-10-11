"""
Parte 5 — invocação de Operations (invoke, invoke-async, operation-status,
operation-results) pelo Call service do servidor OPC UA.
"""
import asyncio

import pytest
from asyncua.common.methods import uamethod

from faaster.api.encoding import b64url_encode
from faaster.api.errors import BadRequestError
from faaster.api.operations import parse_duration
from faaster.extensions.method_binder import MethodBinder

from .conftest import AAS_ID, OPERATIONAL_ID, SHOWCASE_ID, encode


ELEMENTS = f"/submodels/{encode(SHOWCASE_ID)}/submodel-elements"


def bind(registry, path, handler):
    """Vincula o handler como o ExtensionLoader faz com os métodos da extensão."""
    registry.get_operation(SHOWCASE_ID, path).binder.bind(uamethod(handler))


async def add(parent, a, b):
    return float(a + b)


async def echo(parent, text):
    return text.upper()


def _error_text(response) -> str:
    return response.json()["messages"][0]["text"]


# -----------------------------------------------------------------------------
# Invocação síncrona
# -----------------------------------------------------------------------------

async def test_invoke_returns_operation_result(client, registry):
    bind(registry, "Add", add)

    body = {"inputArguments": [
        {"value": {"modelType": "Property", "idShort": "a", "valueType": "xs:int", "value": "2"}},
        {"value": {"modelType": "Property", "idShort": "b", "valueType": "xs:double", "value": "0.25"}},
    ]}
    response = await client.post(f"{ELEMENTS}/Add/invoke", json=body)

    assert response.status_code == 200
    assert response.json() == {
        "executionState": "Completed",
        "success": True,
        "outputArguments": [
            {"value": {"modelType": "Property", "idShort": "sum", "valueType": "xs:double", "value": "2.25"}},
        ],
    }


async def test_invoke_uses_model_default_for_missing_input(client, registry):
    bind(registry, "Add", add)

    body = {"inputArguments": [{"value": {"modelType": "Property", "idShort": "a", "value": "2"}}]}
    result = (await client.post(f"{ELEMENTS}/Add/invoke", json=body)).json()

    # b = 1.5 vem do valor declarado no modelo
    assert result["outputArguments"][0]["value"]["value"] == "3.5"


async def test_invoke_value_only(client, registry):
    bind(registry, "Add", add)

    response = await client.post(
        f"{ELEMENTS}/Add/invoke/$value",
        json={"inputArguments": {"a": 40, "b": 2}, "clientTimeoutDuration": "PT10S"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "executionState": "Completed",
        "success": True,
        "outputArguments": {"sum": 42.0},
    }


async def test_invoke_nested_operation(client, registry):
    bind(registry, "Tools.Echo", echo)

    response = await client.post(
        f"{ELEMENTS}/Tools.Echo/invoke/$value", json={"inputArguments": {"text": "faaster"}}
    )

    assert response.json()["outputArguments"] == {"echo": "FAASTER"}


async def test_invoke_via_shell_superpath(client, registry):
    bind(registry, "Add", add)

    url = f"/shells/{encode(AAS_ID)}/submodels/{encode(SHOWCASE_ID)}/submodel-elements/Add/invoke/$value"
    response = await client.post(url, json={"inputArguments": {"a": 1}})

    assert response.json()["outputArguments"] == {"sum": 2.5}


async def test_invoke_without_outputs(client, registry):
    calls = []

    async def reset(parent):
        calls.append(parent)

    bind(registry, "Reset", reset)

    response = await client.post(f"{ELEMENTS}/Reset/invoke", json={})

    assert response.json() == {"executionState": "Completed", "success": True, "outputArguments": []}
    assert len(calls) == 1


# -----------------------------------------------------------------------------
# Falhas durante a execução: 200 com executionState Failed/Timeout
# -----------------------------------------------------------------------------

async def test_handler_exception_is_failed_result(client, registry):
    async def broken(parent, a, b):
        raise RuntimeError("PLC offline")

    bind(registry, "Add", broken)

    response = await client.post(f"{ELEMENTS}/Add/invoke/$value", json={"inputArguments": {"a": 1}})

    assert response.status_code == 200
    result = response.json()
    assert result["executionState"] == "Failed"
    assert result["success"] is False
    assert result["messages"][0]["code"] == "BadUnexpectedError"


async def test_client_timeout(client, registry):
    async def slow(parent, a, b):
        await asyncio.sleep(5)

    bind(registry, "Add", slow)

    response = await client.post(
        f"{ELEMENTS}/Add/invoke/$value",
        json={"inputArguments": {"a": 1}, "clientTimeoutDuration": "PT0.05S"},
    )

    result = response.json()
    assert result["executionState"] == "Timeout"
    assert result["success"] is False


# -----------------------------------------------------------------------------
# Erros reconhecidos antes da execução
# -----------------------------------------------------------------------------

async def test_unbound_operation_is_not_implemented(client):
    response = await client.post(f"{ELEMENTS}/Add/invoke", json={})

    assert response.status_code == 501
    assert "extension" in _error_text(response)


async def test_invoke_on_non_operation_is_method_not_allowed(client):
    url = f"/submodels/{encode(OPERATIONAL_ID)}/submodel-elements/Temperature/invoke"
    assert (await client.post(url, json={})).status_code == 405


async def test_get_on_invoke_is_method_not_allowed(client):
    assert (await client.get(f"{ELEMENTS}/Add/invoke")).status_code == 405


async def test_unknown_operation_is_not_found(client):
    assert (await client.post(f"{ELEMENTS}/Missing/invoke", json={})).status_code == 404


async def test_inoutput_variables_are_not_implemented(client, registry):
    bind(registry, "Swap", add)

    response = await client.post(f"{ELEMENTS}/Swap/invoke", json={})

    assert response.status_code == 501
    assert "inoutputVariables" in _error_text(response)


@pytest.mark.parametrize("body", [
    {"inputArguments": {"b": 1.0}},                      # falta "a" (sem valor padrão)
    {"inputArguments": {"a": 1, "c": 2}},                # argumento desconhecido
    {"inputArguments": {"a": "um"}},                     # valor inválido para xs:int
    {"inputArguments": {"a": 40000}},                    # fora do Int16 do nó OPC UA
    {"inputArguments": [1, 2]},                          # ValueOnly exige objeto
    {"inoutputArguments": {"x": 1}, "inputArguments": {"a": 1}},
    {"inputArguments": {"a": 1}, "clientTimeoutDuration": "30s"},
    {"inputArguments": {"a": 1}, "clientTimeoutDuration": "-PT1S"},
])
async def test_invalid_request_is_bad_request(client, registry, body):
    called = []

    async def spy(parent, a, b):
        called.append(a)
        return 0.0

    bind(registry, "Add", spy)

    response = await client.post(f"{ELEMENTS}/Add/invoke/$value", json=body)

    assert response.status_code == 400
    assert called == []


async def test_normal_invoke_requires_operation_variables(client, registry):
    bind(registry, "Add", add)

    response = await client.post(f"{ELEMENTS}/Add/invoke", json={"inputArguments": [{"a": 1}]})
    assert response.status_code == 400


# -----------------------------------------------------------------------------
# Invocação assíncrona
# -----------------------------------------------------------------------------

async def _wait_done(client, status_url, attempts=100):
    for _ in range(attempts):
        response = await client.get(status_url)
        if response.status_code == 302:
            return response
        await asyncio.sleep(0.01)
    raise AssertionError("operation did not finish")


async def test_invoke_async_lifecycle(client, registry):
    release = asyncio.Event()

    async def gated(parent, a, b):
        await release.wait()
        return float(a * b)

    bind(registry, "Add", gated)

    response = await client.post(
        f"{ELEMENTS}/Add/invoke-async",
        json={
            "inputArguments": [{"value": {"modelType": "Property", "idShort": "a", "value": "4"}}],
            "clientTimeoutDuration": "PT10S",
        },
    )
    assert response.status_code == 202
    handle = b64url_encode(response.json()["handleId"])
    status_url = response.headers["location"]
    assert status_url.endswith(f"/submodel-elements/Add/operation-status/{handle}")

    running = await client.get(status_url)
    assert running.status_code == 200
    assert running.json() == {"executionState": "Running"}

    release.set()
    done = await _wait_done(client, status_url)
    assert done.headers["location"].endswith(f"/Add/operation-results/{handle}")

    result = (await client.get(done.headers["location"])).json()
    assert result["executionState"] == "Completed"
    assert result["outputArguments"][0]["value"]["value"] == "6.0"

    value_only = (await client.get(f"{ELEMENTS}/Add/operation-results/{handle}/$value")).json()
    assert value_only["outputArguments"] == {"sum": 6.0}


async def test_invoke_async_value_only_redirects_to_value_only_result(client, registry):
    bind(registry, "Add", add)

    response = await client.post(
        f"{ELEMENTS}/Add/invoke-async/$value",
        json={"inputArguments": {"a": 1, "b": 1}, "clientTimeoutDuration": "PT10S"},
    )
    assert response.status_code == 202

    done = await _wait_done(client, response.headers["location"])
    assert done.headers["location"].endswith("/$value")
    assert (await client.get(done.headers["location"])).json()["outputArguments"] == {"sum": 2.0}


async def test_invoke_async_via_superpath(client, registry):
    bind(registry, "Add", add)

    base = f"/shells/{encode(AAS_ID)}/submodels/{encode(SHOWCASE_ID)}/submodel-elements/Add"
    response = await client.post(
        f"{base}/invoke-async/$value",
        json={"inputArguments": {"a": 1}, "clientTimeoutDuration": "PT10S"},
    )

    assert f"/shells/{encode(AAS_ID)}/" in response.headers["location"]
    done = await _wait_done(client, response.headers["location"])
    assert (await client.get(done.headers["location"])).json()["outputArguments"] == {"sum": 2.5}


async def test_invoke_async_requires_client_timeout(client, registry):
    bind(registry, "Add", add)

    response = await client.post(f"{ELEMENTS}/Add/invoke-async", json={"inputArguments": []})
    assert response.status_code == 400


async def test_invoke_async_validates_before_accepting(client, registry):
    bind(registry, "Add", add)

    response = await client.post(
        f"{ELEMENTS}/Add/invoke-async/$value",
        json={"inputArguments": {"a": "x"}, "clientTimeoutDuration": "PT10S"},
    )
    assert response.status_code == 400


async def test_unknown_handle_is_not_found(client):
    url = f"{ELEMENTS}/Add/operation-status/{b64url_encode('nope')}"
    assert (await client.get(url)).status_code == 404


async def test_handle_belongs_to_its_operation(client, registry):
    bind(registry, "Add", add)
    response = await client.post(
        f"{ELEMENTS}/Add/invoke-async/$value",
        json={"inputArguments": {"a": 1}, "clientTimeoutDuration": "PT10S"},
    )
    handle = b64url_encode(response.json()["handleId"])

    assert (await client.get(f"{ELEMENTS}/Reset/operation-status/{handle}")).status_code == 404


async def test_invalid_handle_encoding_is_bad_request(client):
    assert (await client.get(f"{ELEMENTS}/Add/operation-results/!!!")).status_code == 400


# -----------------------------------------------------------------------------
# Unidades
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("text, seconds", [
    ("PT30S", 30),
    ("PT0.5S", 0.5),
    ("PT1M30S", 90),
    ("PT2H", 7200),
    ("P1DT1S", 86401),
])
def test_parse_duration(text, seconds):
    assert parse_duration(text) == seconds


@pytest.mark.parametrize("text", ["30", "P", "PT", "-PT1S", 30, None])
def test_parse_duration_rejects(text):
    with pytest.raises(BadRequestError):
        parse_duration(text)


def test_method_binder_is_awaited_by_asyncua():
    # sem isso o asyncua roda o binder numa thread e a chamada OPC UA falha
    assert asyncio.iscoroutinefunction(MethodBinder())

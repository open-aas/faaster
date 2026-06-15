"""
Testes do GDSRegistrationManager com GDSClient mockado.

Comportamento coberto (OPC 10000-12 §6.4, Figura 11):
    - 0 resultados → RegisterApplication
    - 1 resultado  → UpdateApplication + reutiliza application_id existente
    - 2+ resultados → RuntimeError
    - unregister quando application_id é None → noop
    - unregister quando application_id definido → UnregisterApplication
    - run() para assim que stop_event é sinalizado
"""
import asyncio
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from asyncua.ua import NodeId, ApplicationType, LocalizedText

from faaster.gds.manager import GDSRegistrationManager
from faaster.gds.models import ApplicationRecord


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_record() -> ApplicationRecord:
    return ApplicationRecord(
        application_uri="urn:faaster:test:server",
        application_type=ApplicationType.Server,
        application_names=[LocalizedText(Text="Faaster Test")],
        product_uri="urn:faaster:product",
        discovery_urls=["opc.tcp://localhost:4840"],
    )


def _make_existing(app_id: NodeId) -> object:
    """Simula um ApplicationRecord vindo do GDS (objecto com application_id)."""
    rec = MagicMock()
    rec.application_id = app_id
    return rec


def _make_client(find_results=None) -> AsyncMock:
    """AsyncMock que funciona como async context manager."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.find_applications.return_value = find_results or []
    client.register_application.return_value = NodeId(100, 0)
    return client


# ------------------------------------------------------------------
# Testes de register()
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_new_application_calls_register():
    client = _make_client(find_results=[])
    manager = GDSRegistrationManager(client=client, record=_make_record())

    app_id = await manager.register()

    client.register_application.assert_called_once()
    assert app_id == NodeId(100, 0)


@pytest.mark.asyncio
async def test_register_new_application_sets_application_id():
    client = _make_client(find_results=[])
    manager = GDSRegistrationManager(client=client, record=_make_record())

    await manager.register()

    assert manager.application_id == NodeId(100, 0)


@pytest.mark.asyncio
async def test_register_existing_calls_update():
    existing_id = NodeId(42, 0)
    client = _make_client(find_results=[_make_existing(existing_id)])
    manager = GDSRegistrationManager(client=client, record=_make_record())

    await manager.register()

    client.update_application.assert_called_once()
    client.register_application.assert_not_called()


@pytest.mark.asyncio
async def test_register_existing_reuses_application_id():
    existing_id = NodeId(42, 0)
    client = _make_client(find_results=[_make_existing(existing_id)])
    manager = GDSRegistrationManager(client=client, record=_make_record())

    await manager.register()

    assert manager.application_id == existing_id


@pytest.mark.asyncio
async def test_register_multiple_results_raises():
    existing_id = NodeId(1, 0)
    client = _make_client(find_results=[
        _make_existing(existing_id),
        _make_existing(NodeId(2, 0)),
    ])
    manager = GDSRegistrationManager(client=client, record=_make_record())

    with pytest.raises(RuntimeError, match="Intervenção manual"):
        await manager.register()


@pytest.mark.asyncio
async def test_register_multiple_does_not_call_register_or_update():
    client = _make_client(find_results=[MagicMock(), MagicMock()])
    manager = GDSRegistrationManager(client=client, record=_make_record())

    with pytest.raises(RuntimeError):
        await manager.register()

    client.register_application.assert_not_called()
    client.update_application.assert_not_called()


# ------------------------------------------------------------------
# Testes de unregister()
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unregister_noop_when_no_application_id():
    client = _make_client()
    manager = GDSRegistrationManager(client=client, record=_make_record())

    await manager.unregister()  # application_id é None

    client.unregister_application.assert_not_called()


@pytest.mark.asyncio
async def test_unregister_calls_unregister_application():
    client = _make_client(find_results=[])
    manager = GDSRegistrationManager(client=client, record=_make_record())
    await manager.register()

    await manager.unregister()

    client.unregister_application.assert_called_once()


@pytest.mark.asyncio
async def test_unregister_clears_application_id():
    client = _make_client(find_results=[])
    manager = GDSRegistrationManager(client=client, record=_make_record())
    await manager.register()

    await manager.unregister()

    assert manager.application_id is None


# ------------------------------------------------------------------
# Testes de run()
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_stops_cleanly_on_stop_event():
    client = _make_client(find_results=[])
    manager = GDSRegistrationManager(
        client=client,
        record=_make_record(),
        renew_interval=3600,
    )
    stop_event = asyncio.Event()

    # Sinaliza o stop logo após iniciar a tarefa
    async def set_stop():
        await asyncio.sleep(0)
        stop_event.set()

    await asyncio.gather(
        manager.run(stop_event),
        set_stop(),
    )

    client.register_application.assert_called_once()
    client.unregister_application.assert_called_once()


@pytest.mark.asyncio
async def test_run_exits_early_on_register_failure():
    client = _make_client()
    client.register_application.side_effect = RuntimeError("GDS unavailable")
    # find_applications retorna [] para acionar register_application
    client.find_applications.return_value = []

    manager = GDSRegistrationManager(client=client, record=_make_record())
    stop_event = asyncio.Event()
    stop_event.set()  # já sinalizado — não vai entrar no while loop de qualquer forma

    # Não deve levantar exceção — log de erro e retorno
    await manager.run(stop_event)

    client.unregister_application.assert_not_called()


# ------------------------------------------------------------------
# Testes de _renew()
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_renew_calls_update_application():
    client = _make_client(find_results=[])
    manager = GDSRegistrationManager(client=client, record=_make_record())
    await manager.register()

    await manager._renew()

    # update deve ter sido chamado no register (existing=0 → register) + _renew
    assert client.update_application.call_count == 1


@pytest.mark.asyncio
async def test_renew_does_not_raise_on_error():
    client = _make_client(find_results=[])
    manager = GDSRegistrationManager(client=client, record=_make_record())
    client.update_application.side_effect = Exception("network error")

    # Não deve propagar a exceção
    await manager._renew()

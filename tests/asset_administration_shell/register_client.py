from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from core.asset_administration_shell.client_registration import AssetClient
from core.asset_administration_shell.utils import Utils


@pytest.mark.asyncio
async def test_aenter_method_called_and_awaited():
    """ test to ensure the __aenter__ method is being called """
    client = AssetClient("opc.tcp://localhost:4840")
    client.__aenter__ = AsyncMock()

    with patch.object(AssetClient, '__aenter__', return_value=False):
        await client.__aenter__()
        client.__aenter__.assert_called_once()


@pytest.mark.asyncio
async def test_aexit_method_called_and_awaited():
    """ test to ensure the init method is being called """
    client = AssetClient("opc.tcp://localhost:4840")
    client.__aexit__ = AsyncMock()

    with patch.object(AssetClient, '__aexit__', return_value=False):
        await client.__aexit__(None, None, None)
        client.__aexit__.assert_called_once()


@pytest.mark.asyncio
async def test_register_server_method():
    url = "opc.tcp://localhost:4840"
    discovery_configuration = MagicMock()
    server = MagicMock()

    server.get_application_uri.return_value = "http://example.com"
    server.product_uri = "http://example.com/product"
    server.registered_endpoint = "opc.tcp://example.com:4840"
    server.application_type = Utils.get_ua_properties().ApplicationType.Server
    server.name = "Test Server"

    client = AssetClient(url=url)
    client._client.uaclient.register_server2 = AsyncMock(return_value="Registered")
    result = await client.register_server(server, discovery_configuration)
    assert result == "Registered"
    client._client.uaclient.register_server2.assert_called_once()


@pytest.mark.asyncio
async def test_client_connect_disconnect_exception():
    url = "opc.tcp://localhost:4840"
    with pytest.raises(ConnectionRefusedError):
        client = AssetClient(url=None)
        await client.__aenter__()

    client = AssetClient(url=url)
    client._client.connect = AsyncMock(side_effect=Exception("Connection failed"))
    with pytest.raises(Exception) as exc_info:
        await client.__aenter__()
    assert "Connection failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_register_server_exception():
    url = "opc.tcp://localhost:4840"
    discovery_configuration = MagicMock()
    server = MagicMock()
    server.get_application_uri.return_value = "http://example.com"
    server.product_uri = "http://example.com/product"
    server.registered_endpoint = "opc.tcp://example.com:4840"
    server.application_type = Utils.get_ua_properties().ApplicationType.Server
    server.name = "Test Server"

    client = AssetClient(url=url)
    client._client.uaclient.register_server2 = AsyncMock(side_effect=Exception("Registration failed"))
    with pytest.raises(Exception) as exc_info:
        await client.register_server(server, discovery_configuration)
    assert "Registration failed" in str(exc_info.value)

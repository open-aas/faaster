from unittest.mock import patch, MagicMock

import pytest

from core.asset_administration_shell.utils import Utils
from core.interfaces.client import IClient

Node = Utils.get_node_type()


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


class Client(IClient):
    """ class implementing the client interface """

    async def register_server(self, server, discovery_configuration=None):
        pass


@pytest.mark.asyncio
async def test_register_server_method_called():
    """ test to ensure the init method is being called """
    mocked_server = AsyncMock()
    client = Client()
    client.register_server = AsyncMock()

    with patch.object(Client, 'register_server', return_value=False):
        await client.register_server(mocked_server)
        client.register_server.assert_called_once()

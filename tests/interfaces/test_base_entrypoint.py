from unittest.mock import MagicMock, patch

import pytest

from core.asset_administration_shell.utils import Utils
from core.interfaces.entrypoint import Entrypoint

Node = Utils.get_node_type()


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


class UserEntrypoint(Entrypoint):
    """ class implementing the entrypoint interface """

    async def init(self):
        pass


@pytest.mark.asyncio
async def test_init():
    """ test to ensure the server is being initialized """
    mock_server = MagicMock()
    user_entrypoint = UserEntrypoint(mock_server)
    assert user_entrypoint.server == mock_server


@pytest.mark.asyncio
async def test_init_method_called():
    """ test to ensure the init method is being called """
    mock_server = MagicMock()
    user_entrypoint = UserEntrypoint(mock_server)
    user_entrypoint.init = AsyncMock()

    with patch.object(UserEntrypoint, 'init', return_value=False):
        await user_entrypoint.init()
        user_entrypoint.init.assert_called_once()

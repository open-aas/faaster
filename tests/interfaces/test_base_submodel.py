from unittest.mock import MagicMock, patch

import pytest

from core.asset_administration_shell.utils import Utils
from core.interfaces.base_submodel import BaseSubmodel

Node = Utils.get_node_type()


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


class Submodel(BaseSubmodel):
    """ class implementing the submodel interface """

    async def init(self, parent: Node):
        pass


@pytest.mark.asyncio
async def test_init():
    """ test to ensure the server is being initialized """
    mock_server = MagicMock()
    submodel = Submodel(mock_server)
    assert submodel.server == mock_server


@pytest.mark.asyncio
async def test_init_method_called():
    """ test to ensure the init method is being called """
    mock_server = MagicMock()
    parent_node = AsyncMock()
    submodel = Submodel(mock_server)
    submodel.init = AsyncMock()

    with patch.object(Submodel, 'init', return_value=False):
        await submodel.init(parent_node)
        submodel.init.assert_called_once()

from unittest.mock import patch, MagicMock

import pytest

from core.asset_administration_shell.methods.event_methods import EventMethods
from core.asset_administration_shell.methods.historize_methods import HistorizeMethods
from core.asset_administration_shell.methods.node_methods import NodeMethods
from core.asset_administration_shell.methods.subscription_methods import SubscriptionMethods
from core.asset_administration_shell.utils import Utils
from core.interfaces.server import IServer

Node = Utils.get_node_type()


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


class Server(IServer):
    """ class implementing the client interface """

    async def init(self):
        pass

    def get_database(self):
        pass

    def get_nodes_historized_from_parser(self) -> dict:
        pass

    def get_server_name(self):
        pass

    def get_server_utils(self) -> Utils:
        pass

    def get_event_methods(self) -> EventMethods:
        pass

    def get_historize_methods(self) -> HistorizeMethods:
        pass

    def get_node_methods(self) -> NodeMethods:
        pass

    def get_subscription_methods(self) -> SubscriptionMethods:
        pass

    def get_uri_server(self):
        pass

    async def set_build_info(self, product_uri, manufacturer_name, product_name, software_version, build_number,
                             build_date):
        pass

    async def register_to_discovery(self, url: str = "opc.tcp://localhost:4840", period: int = 60):
        pass

    async def task_registration(self, url, period):
        pass

    async def register_namespace(self, uri: str):
        pass

    async def load_data_type_definitions(self):
        pass

    def set_endpoint(self, url: str):
        pass

    async def add_method_to_server(self, name, func, input_type=None, output_type=None):
        pass

    async def import_xml(self, path=None, xmlstring=None, ignore_missing_refs=False):
        pass

    async def register_server(self, server, discovery_configuration=None):
        pass


@pytest.mark.asyncio
async def test_init_method_called():
    """ test to ensure the init method is being called """
    server = Server()
    server.init = AsyncMock()

    with patch.object(Server, 'init', return_value=False):
        await server.init()
        server.init.assert_called_once()


@pytest.mark.asyncio
async def test_get_database_method_called():
    """ test to ensure the init method is being called """
    server = Server()
    server.get_database = MagicMock()

    with patch.object(Server, 'get_database', return_value=False):
        server.get_database()
        server.get_database.assert_called_once()


@pytest.mark.asyncio
async def test_get_nodes_historized_from_parser_method_called():
    """ test to ensure the init method is being called """
    server = Server()
    server.get_nodes_historized_from_parser = MagicMock()

    with patch.object(Server, 'get_nodes_historized_from_parser', return_value=False):
        server.get_nodes_historized_from_parser()
        server.get_nodes_historized_from_parser.assert_called_once()


@pytest.mark.asyncio
async def test_get_server_name_called():
    """ test to ensure the init method is being called """
    server = Server()
    server.get_server_name = MagicMock()

    with patch.object(Server, 'get_server_name'):
        server.get_server_name()
        server.get_server_name.assert_called_once()


@pytest.mark.asyncio
async def test_get_server_utils_called():
    """ test to ensure the init method is being called """
    server = Server()
    server.get_server_utils = MagicMock()

    with patch.object(Server, 'get_server_utils'):
        server.get_server_utils()
        server.get_server_utils.assert_called_once()


@pytest.mark.asyncio
async def test_get_historize_methods_called():
    """ test to ensure the init method is being called """
    server = Server()
    server.get_historize_methods = MagicMock()

    with patch.object(Server, 'get_historize_methods'):
        server.get_historize_methods()
        server.get_historize_methods.assert_called_once()


@pytest.mark.asyncio
async def test_get_node_method_called():
    """ test to ensure the init method is being called """
    server = Server()
    server.get_node_methods = MagicMock()

    with patch.object(Server, 'get_node_methods'):
        server.get_node_methods()
        server.get_node_methods.assert_called_once()


@pytest.mark.asyncio
async def test_get_subscription_method_called():
    """ test to ensure the init method is being called """
    server = Server()
    server.get_subscription_methods = MagicMock()

    with patch.object(Server, 'get_subscription_methods'):
        server.get_subscription_methods()
        server.get_subscription_methods.assert_called_once()


@pytest.mark.asyncio
async def test_get_uri_server_methods_called():
    """ test to ensure the init method is being called """
    server = Server()
    server.get_uri_server = MagicMock()

    with patch.object(Server, 'get_subscription_methods'):
        server.get_uri_server()
        server.get_uri_server.assert_called_once()

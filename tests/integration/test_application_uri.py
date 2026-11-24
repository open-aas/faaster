"""--application-uri sets the OPC UA ApplicationUri (needed to register each twin in a GDS and
to match the URI in its X.509 certificate). Without it every instance used the ProductUri."""
from unittest.mock import MagicMock

from asyncua import Server

from faaster.infra.aas_server import OPCUAServer


def _args(*extra):
    import sys
    from unittest.mock import patch

    from faaster.cli import aas_parser_arguments

    with patch.object(sys, "argv", ["server.py", "-m", "m.json", "--host", "127.0.0.1",
                                    "--port", "0", *extra]):
        return aas_parser_arguments()


def _server(opcua):
    return OPCUAServer(opcua_server=opcua, address_space=MagicMock(), parser=MagicMock(),
                       extension_loader=MagicMock(), hda_manager=None)


async def test_application_uri_is_set():
    opcua = Server()
    await _server(opcua).setup(_args("--application-uri", "urn:ftm:twin:motor-01"))

    assert opcua.get_application_uri() == "urn:ftm:twin:motor-01"


async def test_default_application_uri_is_unchanged():
    """Without the option the product URI is used, as before (shared by all instances)."""
    opcua = Server()
    await _server(opcua).setup(_args())

    assert opcua.get_application_uri() == "urn:faaster:server"


def test_cli_accepts_application_uri(monkeypatch):
    import sys

    from faaster.cli import aas_parser_arguments

    monkeypatch.setattr(sys, "argv", ["server.py", "-m", "m.json",
                                      "--application-uri", "urn:ftm:twin:x"])
    assert aas_parser_arguments().application_uri == "urn:ftm:twin:x"

"""
Fixtures da API HTTP/REST.

Monta o address space real (asyncua sem rede) a partir de fixtures/model.json
e expõe um cliente httpx ligado à aplicação FastAPI via ASGI.
"""
from pathlib import Path

import httpx
import pytest
from asyncua import Server

from faaster.api import AASRepository, create_app
from faaster.api.encoding import b64url_encode
from faaster.asset_administration_shell import AssetAdministrationShell
from faaster.parser import NodeRegistry


MODEL = Path(__file__).parent / "fixtures" / "model.json"
BASE_PATH = "/api/v3"

OPERATIONAL_ID = "urn:faaster:test:sm:operational"
NAMEPLATE_ID = "urn:faaster:test:sm:nameplate"
SHOWCASE_ID = "urn:faaster:test:sm:showcase"

AAS_ID = "urn:faaster:test:aas:1"
OTHER_AAS_ID = "urn:faaster:test:aas:2"

CD_TEMPERATURE_ID = "urn:faaster:test:cd:temperature"
CD_CELSIUS_ID = "urn:faaster:test:cd:celsius"
CD_UNUSED_ID = "urn:faaster:test:cd:unused"


def encode(identifier: str) -> str:
    return b64url_encode(identifier)


@pytest.fixture
async def parsed_aas():
    from argparse import Namespace

    args = Namespace(url_database=None, http_port=None)
    aas = AssetAdministrationShell(args)

    server: Server = aas._opcua_server
    await server.init()
    await server.register_namespace("urn:faaster:server")
    aas.address_space.set_namespace("urn:faaster:server")
    await aas.parser.parse(str(MODEL))

    try:
        yield aas
    finally:
        await server.iserver.stop()


@pytest.fixture
def registry(parsed_aas) -> NodeRegistry:
    return parsed_aas.node_registry


@pytest.fixture
async def client(parsed_aas):
    app = create_app(
        repository=AASRepository(parsed_aas.parser.document),
        registry=parsed_aas.node_registry,
        base_path=BASE_PATH,
        address_space=parsed_aas.address_space,
        model_sync=parsed_aas.parser,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=f"http://faaster{BASE_PATH}") as c:
        yield c

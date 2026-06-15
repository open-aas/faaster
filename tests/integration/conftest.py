"""
Fixtures compartilhadas para testes de integração Sprint 3.

Usa asyncua.Server com init() apenas (sem start/stop de rede),
o que é suficiente para todas as operações de address space.
"""
import pytest
from asyncua import Server

from faaster.infra.address_space import AddressSpaceAdapter, NodeAdapter


FAASTER_TEST_NS = "urn:faaster:integration:test"


@pytest.fixture
async def opcua_server():
    server = Server()
    await server.init()
    try:
        yield server
    finally:
        # bserver (network layer) é None quando start() não foi chamado;
        # apenas o iserver (address space in-memory) precisa de cleanup.
        await server.iserver.stop()


@pytest.fixture
async def address_space(opcua_server):
    await opcua_server.register_namespace(FAASTER_TEST_NS)
    as_ = AddressSpaceAdapter(opcua_server)
    as_.set_namespace(FAASTER_TEST_NS)
    return as_


@pytest.fixture
async def objects_node(opcua_server):
    return NodeAdapter(opcua_server.get_objects_node())

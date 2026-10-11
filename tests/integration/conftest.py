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


# -----------------------------------------------------------------------------
# TimescaleDB para os testes de HDA
#
# FAASTER_TEST_TIMESCALE_URL=postgresql://user:pass@host:5432 usa um servidor
# existente; sem ela, sobe um container descartável (Docker) para a sessão.
# Sem nenhum dos dois, os testes de HDA são pulados.
# -----------------------------------------------------------------------------

import asyncio
import os
import shutil
import socket
import subprocess
import time
import uuid

import asyncpg

from faaster.infra.database_timescale import TimescaleDatabase


TIMESCALE_IMAGE = os.environ.get("FAASTER_TEST_TIMESCALE_IMAGE", "timescale/timescaledb:latest-pg17")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def _accepts_connections(url: str) -> bool:
    try:
        conn = await asyncpg.connect(dsn=f"{url}/postgres", timeout=2)
    except (OSError, asyncpg.PostgresError, asyncio.TimeoutError):
        return False
    try:
        return await conn.fetchval("SELECT 1") == 1
    finally:
        await conn.close()


def _wait_ready(url: str, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if asyncio.run(_accepts_connections(url)):
            return
        time.sleep(0.5)
    raise RuntimeError(f"TimescaleDB not ready at {url}")


@pytest.fixture(scope="session")
def timescale_url():
    url = os.environ.get("FAASTER_TEST_TIMESCALE_URL")
    if url:
        yield url.rstrip("/")
        return

    if shutil.which("docker") is None:
        pytest.skip("HDA tests need Docker or FAASTER_TEST_TIMESCALE_URL")

    port = _free_port()
    name = f"faaster-test-timescale-{uuid.uuid4().hex[:8]}"
    started = subprocess.run(
        [
            "docker", "run", "-d", "--rm", "--name", name,
            "-e", "POSTGRES_USER=faaster", "-e", "POSTGRES_PASSWORD=faaster",
            "-p", f"127.0.0.1:{port}:5432", TIMESCALE_IMAGE,
        ],
        capture_output=True,
        text=True,
    )
    if started.returncode != 0:
        pytest.skip(f"cannot start TimescaleDB container: {started.stderr.strip()}")

    try:
        url = f"postgresql://faaster:faaster@127.0.0.1:{port}"
        _wait_ready(url)
        yield url
    finally:
        subprocess.run(["docker", "stop", name], capture_output=True)


@pytest.fixture
async def timescale_db(timescale_url):
    """TimescaleDatabase conectado a uma database nova, apagada no fim do teste."""
    db_name = f"faaster_test_{uuid.uuid4().hex[:12]}"
    db = TimescaleDatabase(url=timescale_url, db_name=db_name)
    await db.connect()
    try:
        yield db
    finally:
        await db.disconnect()
        conn = await asyncpg.connect(dsn=f"{timescale_url}/postgres")
        try:
            await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
        finally:
            await conn.close()

"""Secure server with the asyncua 1.1 API: TrustStore(trust_locations, crl_locations) wrapped in
a CertificateValidator. The previous code passed unsupported keyword arguments and crashed on
startup whenever --pki-dir was used."""
import asyncio
import shutil
import socket

import pytest
from asyncua import Client, Server, ua
from asyncua.crypto.cert_gen import setup_self_signed_certificate
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from cryptography.x509.oid import ExtendedKeyUsageOID

from faaster.security.certificate_store import CertificateStore
from faaster.security.server_security import (
    SecurityMode,
    SecurityPolicy,
    bootstrap_pki,
    build_security_policy_list,
    configure_server_security,
)


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def _client_cert(directory, uri):
    key, cert = directory / f"{uri.split(':')[-1]}.pem", directory / f"{uri.split(':')[-1]}.der"
    await setup_self_signed_certificate(key, cert, uri, "localhost",
                                        [ExtendedKeyUsageOID.CLIENT_AUTH], {"commonName": uri})
    return cert, key


async def _connect(port, cert, key, uri):
    client = Client(f"opc.tcp://127.0.0.1:{port}", timeout=5)
    client.application_uri = uri
    await client.set_security(SecurityPolicyBasic256Sha256, str(cert), str(key),
                              mode=ua.MessageSecurityMode.SignAndEncrypt)
    async with client:
        return await client.nodes.server_state.read_value()


@pytest.fixture
async def secure_server(tmp_path):
    store = CertificateStore(tmp_path / "pki")
    await bootstrap_pki(store, "Faaster", "urn:test:faaster")
    trusted, trusted_key = await _client_cert(tmp_path, "urn:test:trusted")
    shutil.copy(trusted, store.trusted_certs_dir / "trusted.der")
    port = _free_port()
    server = Server()
    await server.init()
    await server.set_application_uri("urn:test:faaster")
    server.set_endpoint(f"opc.tcp://127.0.0.1:{port}")
    policies = build_security_policy_list([SecurityPolicy.basic256], SecurityMode.sign_and_encrypt)
    await configure_server_security(server, store, policies)
    async with server:
        yield port, (trusted, trusted_key), tmp_path


async def test_trusted_client_connects_and_unknown_client_is_refused(secure_server):
    port, (cert, key), tmp = secure_server

    assert await _connect(port, cert, key, "urn:test:trusted") == ua.ServerState.Running

    other, other_key = await _client_cert(tmp, "urn:test:stranger")
    with pytest.raises(Exception):  # noqa: B017 - BadSecurityChecksFailed / connection closed
        await asyncio.wait_for(_connect(port, other, other_key, "urn:test:stranger"), 10)

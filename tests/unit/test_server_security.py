import pytest
from asyncua import ua
from faaster.security.server_security import (
    SecurityPolicy,
    SecurityMode,
    build_security_policy_list,
    _accept_pending,
)
from faaster.security.certificate_store import CertificateStore


# ------------------------------------------------------------------
# build_security_policy_list
# ------------------------------------------------------------------

def test_no_policies_returns_no_security():
    result = build_security_policy_list(policies=None)
    assert result == [ua.SecurityPolicyType.NoSecurity]


def test_empty_policies_returns_no_security():
    result = build_security_policy_list(policies=[])
    assert result == [ua.SecurityPolicyType.NoSecurity]


def test_allow_anonymous_adds_no_security_first():
    result = build_security_policy_list(
        policies=[SecurityPolicy.basic256],
        mode=SecurityMode.sign_and_encrypt,
        allow_anonymous=True,
    )
    assert result[0] == ua.SecurityPolicyType.NoSecurity
    assert ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt in result


def test_basic256_sign():
    result = build_security_policy_list(
        policies=[SecurityPolicy.basic256],
        mode=SecurityMode.sign,
    )
    assert ua.SecurityPolicyType.Basic256Sha256_Sign in result
    assert ua.SecurityPolicyType.NoSecurity not in result


def test_basic256_sign_and_encrypt():
    result = build_security_policy_list(
        policies=[SecurityPolicy.basic256],
        mode=SecurityMode.sign_and_encrypt,
    )
    assert ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt in result


def test_aes128_sign():
    result = build_security_policy_list(
        policies=[SecurityPolicy.aes128],
        mode=SecurityMode.sign,
    )
    assert ua.SecurityPolicyType.Aes128Sha256RsaOaep_Sign in result


def test_aes128_sign_and_encrypt():
    result = build_security_policy_list(
        policies=[SecurityPolicy.aes128],
        mode=SecurityMode.sign_and_encrypt,
    )
    assert ua.SecurityPolicyType.Aes128Sha256RsaOaep_SignAndEncrypt in result


def test_aes256_sign():
    result = build_security_policy_list(
        policies=[SecurityPolicy.aes256],
        mode=SecurityMode.sign,
    )
    assert ua.SecurityPolicyType.Aes256Sha256RsaPss_Sign in result


def test_aes256_sign_and_encrypt():
    result = build_security_policy_list(
        policies=[SecurityPolicy.aes256],
        mode=SecurityMode.sign_and_encrypt,
    )
    assert ua.SecurityPolicyType.Aes256Sha256RsaPss_SignAndEncrypt in result


def test_multiple_policies():
    result = build_security_policy_list(
        policies=[SecurityPolicy.basic256, SecurityPolicy.aes128],
        mode=SecurityMode.sign_and_encrypt,
    )
    assert ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt in result
    assert ua.SecurityPolicyType.Aes128Sha256RsaOaep_SignAndEncrypt in result
    assert len(result) == 2


# ------------------------------------------------------------------
# _accept_pending
# ------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    return CertificateStore(tmp_path / "pki")


def test_accept_pending_moves_der(store):
    (store.rejected_dir / "client.der").write_bytes(b"\x00")
    moved = _accept_pending(store)
    assert moved == 1
    assert (store.trusted_certs_dir / "client.der").exists()
    assert not (store.rejected_dir / "client.der").exists()


def test_accept_pending_moves_pem(store):
    (store.rejected_dir / "client.pem").write_bytes(b"\x00")
    moved = _accept_pending(store)
    assert moved == 1
    assert (store.trusted_certs_dir / "client.pem").exists()


def test_accept_pending_moves_crt(store):
    (store.rejected_dir / "client.crt").write_bytes(b"\x00")
    moved = _accept_pending(store)
    assert moved == 1


def test_accept_pending_ignores_unknown_extensions(store):
    (store.rejected_dir / "README.txt").write_bytes(b"ignore me")
    moved = _accept_pending(store)
    assert moved == 0
    assert (store.rejected_dir / "README.txt").exists()


def test_accept_pending_empty_dir_returns_zero(store):
    assert _accept_pending(store) == 0


def test_accept_pending_multiple_files(store):
    for i in range(3):
        (store.rejected_dir / f"cert_{i}.der").write_bytes(b"\x00")
    moved = _accept_pending(store)
    assert moved == 3
    assert len(list(store.trusted_certs_dir.iterdir())) == 3

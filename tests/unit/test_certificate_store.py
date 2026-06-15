import stat
import pytest
from types import SimpleNamespace
from faaster.security.certificate_store import (
    CertificateStore,
    TRUSTED_CERTIFICATES,
    TRUSTED_CRLS,
    ISSUER_CERTIFICATES,
    ISSUER_CRLS,
    ALL_LISTS,
)


@pytest.fixture
def store(tmp_path):
    return CertificateStore(tmp_path / "pki")


def test_dirs_created(tmp_path):
    pki = tmp_path / "pki"
    store = CertificateStore(pki)
    assert (pki / "own" / "certs").is_dir()
    assert (pki / "own" / "private").is_dir()
    assert (pki / "trusted" / "certs").is_dir()
    assert (pki / "trusted" / "crl").is_dir()
    assert (pki / "issuers" / "certs").is_dir()
    assert (pki / "issuers" / "crl").is_dir()
    assert (pki / "rejected").is_dir()


def test_has_own_certificate_false_initially(store):
    assert store.has_own_certificate() is False


def test_save_and_load_own_certificate(store):
    cert_der = b"\x30\x82\x01\x00"
    store.save_own_certificate(cert_der)
    assert store.has_own_certificate() is False  # key still missing
    assert store.load_own_certificate() == cert_der


def test_has_own_certificate_true_after_both_saved(store):
    store.save_own_certificate(b"\x00" * 4)
    store.save_own_private_key(b"-----BEGIN RSA PRIVATE KEY-----\n")
    assert store.has_own_certificate() is True


def test_private_key_permissions(store):
    store.save_own_private_key(b"key-bytes")
    mode = store.own_key_path.stat().st_mode & 0o777
    assert mode == 0o600


def test_load_own_certificate_missing_returns_none(store):
    assert store.load_own_certificate() is None


def test_load_own_private_key_missing_returns_none(store):
    assert store.load_own_private_key() is None


def test_save_trusted_certificate(store):
    store.save_trusted_certificate(b"\xAA\xBB", "client.der")
    assert (store.trusted_certs_dir / "client.der").read_bytes() == b"\xAA\xBB"


def test_save_rejected(store):
    store.save_rejected(b"\xFF\xFE", "unknown.der")
    assert (store.rejected_dir / "unknown.der").read_bytes() == b"\xFF\xFE"


def test_apply_trust_list_trusted_certs(store):
    trust_list = SimpleNamespace(
        SpecifiedLists=TRUSTED_CERTIFICATES,
        TrustedCertificates=[b"\x01\x02", b"\x03\x04"],
        TrustedCrls=[],
        IssuerCertificates=[],
        IssuerCrls=[],
    )
    store.apply_trust_list(trust_list)
    files = list(store.trusted_certs_dir.iterdir())
    assert len(files) == 2


def test_apply_trust_list_replaces_existing(store):
    store.save_trusted_certificate(b"\xDE\xAD", "old.der")
    trust_list = SimpleNamespace(
        SpecifiedLists=TRUSTED_CERTIFICATES,
        TrustedCertificates=[b"\xBE\xEF"],
        TrustedCrls=[],
        IssuerCertificates=[],
        IssuerCrls=[],
    )
    store.apply_trust_list(trust_list)
    files = list(store.trusted_certs_dir.iterdir())
    assert len(files) == 1
    assert files[0].read_bytes() == b"\xBE\xEF"


def test_apply_trust_list_issuer_certs(store):
    trust_list = SimpleNamespace(
        SpecifiedLists=ISSUER_CERTIFICATES,
        TrustedCertificates=[],
        TrustedCrls=[],
        IssuerCertificates=[b"\xCA\xCA"],
        IssuerCrls=[],
    )
    store.apply_trust_list(trust_list)
    files = list(store.issuers_certs_dir.iterdir())
    assert len(files) == 1


def test_apply_trust_list_all_masks(store):
    trust_list = SimpleNamespace(
        SpecifiedLists=ALL_LISTS,
        TrustedCertificates=[b"\x01"],
        TrustedCrls=[b"\x02"],
        IssuerCertificates=[b"\x03"],
        IssuerCrls=[b"\x04"],
    )
    store.apply_trust_list(trust_list)
    assert len(list(store.trusted_certs_dir.iterdir())) == 1
    assert len(list(store.trusted_crls_dir.iterdir())) == 1
    assert len(list(store.issuers_certs_dir.iterdir())) == 1
    assert len(list(store.issuers_crls_dir.iterdir())) == 1


def test_apply_trust_list_selective_mask_does_not_touch_others(store):
    store.save_trusted_certificate(b"\xAA", "existing.der")
    trust_list = SimpleNamespace(
        SpecifiedLists=ISSUER_CERTIFICATES,
        TrustedCertificates=[],
        TrustedCrls=[],
        IssuerCertificates=[b"\xBB"],
        IssuerCrls=[],
    )
    store.apply_trust_list(trust_list)
    # trusted/ deve permanecer intacto
    assert len(list(store.trusted_certs_dir.iterdir())) == 1

import hashlib
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtendedKeyUsageOID

from faaster.security.crypto_utils import (
    generate_self_signed_certificate,
    generate_csr,
    load_private_key,
    certificate_thumbprint,
)


@pytest.fixture(scope="module")
def cert_and_key():
    return generate_self_signed_certificate(
        common_name="TestServer",
        application_uri="urn:faaster:test",
        san_dns=["localhost"],
        san_ips=["127.0.0.1"],
    )


def test_returns_bytes(cert_and_key):
    cert_der, key_pem = cert_and_key
    assert isinstance(cert_der, bytes)
    assert isinstance(key_pem, bytes)


def test_cert_is_valid_x509(cert_and_key):
    cert_der, _ = cert_and_key
    cert = x509.load_der_x509_certificate(cert_der)
    assert cert is not None


def test_common_name(cert_and_key):
    cert_der, _ = cert_and_key
    cert = x509.load_der_x509_certificate(cert_der)
    cn = cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value
    assert cn == "TestServer"


def test_san_uri(cert_and_key):
    cert_der, _ = cert_and_key
    cert = x509.load_der_x509_certificate(cert_der)
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    uris = san.get_values_for_type(x509.UniformResourceIdentifier)
    assert "urn:faaster:test" in uris


def test_san_dns(cert_and_key):
    cert_der, _ = cert_and_key
    cert = x509.load_der_x509_certificate(cert_der)
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    dns_names = san.get_values_for_type(x509.DNSName)
    assert "localhost" in dns_names


def test_san_ip(cert_and_key):
    import ipaddress
    cert_der, _ = cert_and_key
    cert = x509.load_der_x509_certificate(cert_der)
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    ips = san.get_values_for_type(x509.IPAddress)
    assert ipaddress.ip_address("127.0.0.1") in ips


def test_basic_constraints_not_ca(cert_and_key):
    cert_der, _ = cert_and_key
    cert = x509.load_der_x509_certificate(cert_der)
    bc = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
    assert bc.ca is False


def test_key_usage(cert_and_key):
    cert_der, _ = cert_and_key
    cert = x509.load_der_x509_certificate(cert_der)
    ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
    assert ku.digital_signature is True
    assert ku.key_encipherment is True
    assert ku.content_commitment is True


def test_extended_key_usage(cert_and_key):
    cert_der, _ = cert_and_key
    cert = x509.load_der_x509_certificate(cert_der)
    eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    oids = list(eku)
    assert ExtendedKeyUsageOID.SERVER_AUTH in oids
    assert ExtendedKeyUsageOID.CLIENT_AUTH in oids


def test_self_signed(cert_and_key):
    cert_der, _ = cert_and_key
    cert = x509.load_der_x509_certificate(cert_der)
    assert cert.issuer == cert.subject


def test_load_private_key(cert_and_key):
    _, key_pem = cert_and_key
    key = load_private_key(key_pem)
    assert key is not None
    assert key.key_size == 2048


def test_thumbprint_format(cert_and_key):
    cert_der, _ = cert_and_key
    thumb = certificate_thumbprint(cert_der)
    assert isinstance(thumb, str)
    assert len(thumb) == 40
    assert thumb == thumb.upper()


def test_thumbprint_matches_sha1(cert_and_key):
    cert_der, _ = cert_and_key
    expected = hashlib.sha1(cert_der).hexdigest().upper()
    assert certificate_thumbprint(cert_der) == expected


def test_generate_csr_is_valid_der(cert_and_key):
    _, key_pem = cert_and_key
    csr_der = generate_csr(
        key_pem=key_pem,
        common_name="TestServer",
        application_uri="urn:faaster:test",
    )
    csr = x509.load_der_x509_csr(csr_der)
    assert csr.is_signature_valid


def test_generate_csr_has_uri_san(cert_and_key):
    _, key_pem = cert_and_key
    csr_der = generate_csr(
        key_pem=key_pem,
        common_name="TestServer",
        application_uri="urn:faaster:test",
        san_dns=["faaster.local"],
    )
    csr = x509.load_der_x509_csr(csr_der)
    san = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    uris = san.get_values_for_type(x509.UniformResourceIdentifier)
    assert "urn:faaster:test" in uris

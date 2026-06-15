"""
Utilitários criptográficos para OPC UA.

Funções:
    generate_self_signed_certificate  — gera par chave+cert X.509 v3 auto-assinado
    generate_csr                      — gera CSR (PKCS#10) a partir de chave existente
    load_private_key                  — carrega chave privada PEM de bytes ou arquivo
    certificate_thumbprint            — retorna SHA-1 thumbprint (hex) de um certificado DER

Requisitos OPC UA para certificados (OPC 10000-6 §6.2.2):
    - Subject: CN deve refletir o nome da aplicação
    - SubjectAltName: URI = applicationUri (obrigatório), DNS/IP opcionais
    - KeyUsage: digitalSignature + keyEncipherment + nonRepudiation
    - ExtendedKeyUsage: serverAuth (1.3.6.1.5.5.7.3.1) + clientAuth (1.3.6.1.5.5.7.3.2)
    - BasicConstraints: CA=False
    - SubjectKeyIdentifier e AuthorityKeyIdentifier presentes
"""
from __future__ import annotations

import hashlib
import ipaddress
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


# RSA-2048 é o mínimo para a política Basic256Sha256 (OPC 10000-7)
_KEY_SIZE = 2048
_PUBLIC_EXPONENT = 65537
_CERT_VALIDITY_DAYS = 365


def generate_self_signed_certificate(
    common_name: str,
    application_uri: str,
    san_dns: list[str] | None = None,
    san_ips: list[str] | None = None,
    validity_days: int = _CERT_VALIDITY_DAYS,
) -> tuple[bytes, bytes]:
    """
    Gera um par (certificado DER, chave privada PEM) auto-assinado compatível
    com OPC UA Basic256Sha256.

    O certificado é usado para bootstrap — conexão inicial ao GDS antes de
    receber um certificado assinado pela CA do GDS.

    Retorna:
        (cert_der: bytes, key_pem: bytes)
    """
    key = rsa.generate_private_key(
        public_exponent=_PUBLIC_EXPONENT,
        key_size=_KEY_SIZE,
    )

    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Faaster"),
    ])

    san_entries: list[x509.GeneralName] = [
        x509.UniformResourceIdentifier(application_uri),
    ]
    for dns in (san_dns or []):
        san_entries.append(x509.DNSName(dns))
    for ip in (san_ips or []):
        san_entries.append(x509.IPAddress(ipaddress.ip_address(ip)))

    now = datetime.now(tz=timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=validity_days))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=True,  # nonRepudiation
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                data_encipherment=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
                ExtendedKeyUsageOID.CLIENT_AUTH,
            ]),
            critical=False,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    cert_der = cert.public_bytes(serialization.Encoding.DER)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return cert_der, key_pem


def generate_csr(
    key_pem: bytes,
    common_name: str,
    application_uri: str,
    san_dns: list[str] | None = None,
    san_ips: list[str] | None = None,
) -> bytes:
    """
    Gera um CSR (Certificate Signing Request — PKCS#10) em DER a partir de
    uma chave privada PEM existente.

    Usado em StartSigningRequest (OPC 10000-12 §7.9.3): o servidor gera o
    par de chaves localmente e envia apenas o CSR ao GDS para assinatura.

    Retorna:
        csr_der: bytes
    """
    key = load_private_key(key_pem)

    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Faaster"),
    ])

    san_entries: list[x509.GeneralName] = [
        x509.UniformResourceIdentifier(application_uri),
    ]
    for dns in (san_dns or []):
        san_entries.append(x509.DNSName(dns))
    for ip in (san_ips or []):
        san_entries.append(x509.IPAddress(ipaddress.ip_address(ip)))

    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(subject)
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=True,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                data_encipherment=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
                ExtendedKeyUsageOID.CLIENT_AUTH,
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    return csr.public_bytes(serialization.Encoding.DER)


def load_private_key(key_pem: bytes):
    """Carrega uma chave privada RSA a partir de bytes PEM."""
    return serialization.load_pem_private_key(key_pem, password=None)


def certificate_thumbprint(cert_der: bytes) -> str:
    """Retorna o SHA-1 thumbprint (hex) de um certificado DER."""
    return hashlib.sha1(cert_der).hexdigest().upper()

"""
OPC UA Certificate Store — Annex F (OPC 10000-12, Tabela 163).

Layout de diretório:

    pki/
    ├── own/
    │   ├── certs/      ← certificado DER do servidor
    │   └── private/    ← chave privada PEM (permissão 0600)
    ├── trusted/
    │   ├── certs/      ← certificados DER de clientes/servidores confiáveis
    │   └── crl/        ← CRLs dos emissores confiáveis
    ├── issuers/
    │   ├── certs/      ← certificados DER das CAs emissoras
    │   └── crl/        ← CRLs das CAs
    └── rejected/       ← certificados rejeitados para análise manual
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

from faaster.log import get_logger

logger = get_logger(__name__)

_OWN_CERT = "server_cert.der"
_OWN_KEY = "server_key.pem"

# TrustListMasks (OPC 10000-12 §7.8.2, Tabela 34)
TRUSTED_CERTIFICATES = 0x01
TRUSTED_CRLS = 0x02
ISSUER_CERTIFICATES = 0x04
ISSUER_CRLS = 0x08
ALL_LISTS = 0x0F


class CertificateStore:
    """
    Gerencia o diretório pki/ conforme Annex F da especificação OPC 10000-12.
    Thread-safe para leitura; gravações são operações atômicas por arquivo.
    """

    def __init__(self, pki_dir: str | Path) -> None:
        root = Path(pki_dir)
        self._own_certs = root / "own" / "certs"
        self._own_private = root / "own" / "private"
        self._trusted_certs = root / "trusted" / "certs"
        self._trusted_crls = root / "trusted" / "crl"
        self._issuers_certs = root / "issuers" / "certs"
        self._issuers_crls = root / "issuers" / "crl"
        self._rejected = root / "rejected"
        self._create_dirs()
        logger.info("certificate_store.initialized", pki_dir=str(root))

    # ------------------------------------------------------------------
    # Inicialização
    # ------------------------------------------------------------------

    def _create_dirs(self) -> None:
        for d in (
            self._own_certs, self._own_private,
            self._trusted_certs, self._trusted_crls,
            self._issuers_certs, self._issuers_crls,
            self._rejected,
        ):
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Certificado e chave próprios
    # ------------------------------------------------------------------

    @property
    def own_cert_path(self) -> Path:
        return self._own_certs / _OWN_CERT

    @property
    def own_key_path(self) -> Path:
        return self._own_private / _OWN_KEY

    def has_own_certificate(self) -> bool:
        return self.own_cert_path.exists() and self.own_key_path.exists()

    def save_own_certificate(self, cert_der: bytes) -> None:
        self.own_cert_path.write_bytes(cert_der)
        logger.info("certificate_store.own_cert_saved", path=str(self.own_cert_path))

    def save_own_private_key(self, key_pem: bytes) -> None:
        self.own_key_path.write_bytes(key_pem)
        # Garante que apenas o dono pode ler a chave privada
        os.chmod(self.own_key_path, stat.S_IRUSR | stat.S_IWUSR)
        logger.info("certificate_store.own_key_saved", path=str(self.own_key_path))

    def load_own_certificate(self) -> bytes | None:
        if not self.own_cert_path.exists():
            return None
        return self.own_cert_path.read_bytes()

    def load_own_private_key(self) -> bytes | None:
        if not self.own_key_path.exists():
            return None
        return self.own_key_path.read_bytes()

    # ------------------------------------------------------------------
    # TrustList — aplicação em bloco vinda do GDS
    # ------------------------------------------------------------------

    def apply_trust_list(self, trust_list: object) -> None:
        """
        Aplica um TrustListDataType OPC UA ao store local, substituindo
        completamente as listas especificadas em SpecifiedLists.

        OPC 10000-12 §7.8.2 — TrustListMasks (Tabela 34).
        """
        masks: int = int(trust_list.SpecifiedLists)

        if masks & TRUSTED_CERTIFICATES:
            self._clear_dir(self._trusted_certs)
            for i, cert in enumerate(trust_list.TrustedCertificates or []):
                self.save_trusted_certificate(bytes(cert), f"trusted_{i:04d}.der")

        if masks & TRUSTED_CRLS:
            self._clear_dir(self._trusted_crls)
            for i, crl in enumerate(trust_list.TrustedCrls or []):
                self.save_trusted_crl(bytes(crl), f"trusted_crl_{i:04d}.crl")

        if masks & ISSUER_CERTIFICATES:
            self._clear_dir(self._issuers_certs)
            for i, cert in enumerate(trust_list.IssuerCertificates or []):
                self.save_issuer_certificate(bytes(cert), f"issuer_{i:04d}.der")

        if masks & ISSUER_CRLS:
            self._clear_dir(self._issuers_crls)
            for i, crl in enumerate(trust_list.IssuerCrls or []):
                self.save_issuer_crl(bytes(crl), f"issuer_crl_{i:04d}.crl")

        logger.info(
            "certificate_store.trust_list_applied",
            masks=hex(masks),
            trusted_certs=len(trust_list.TrustedCertificates or []),
            issuer_certs=len(trust_list.IssuerCertificates or []),
        )

    # ------------------------------------------------------------------
    # Gravação individual de certificados e CRLs
    # ------------------------------------------------------------------

    def save_trusted_certificate(self, cert_der: bytes, filename: str) -> None:
        (self._trusted_certs / filename).write_bytes(cert_der)

    def save_trusted_crl(self, crl_der: bytes, filename: str) -> None:
        (self._trusted_crls / filename).write_bytes(crl_der)

    def save_issuer_certificate(self, cert_der: bytes, filename: str) -> None:
        (self._issuers_certs / filename).write_bytes(cert_der)

    def save_issuer_crl(self, crl_der: bytes, filename: str) -> None:
        (self._issuers_crls / filename).write_bytes(crl_der)

    def save_rejected(self, cert_der: bytes, filename: str) -> None:
        (self._rejected / filename).write_bytes(cert_der)

    # ------------------------------------------------------------------
    # Propriedades de path para integração com asyncua
    # ------------------------------------------------------------------

    @property
    def trusted_certs_dir(self) -> Path:
        return self._trusted_certs

    @property
    def trusted_crls_dir(self) -> Path:
        return self._trusted_crls

    @property
    def issuers_certs_dir(self) -> Path:
        return self._issuers_certs

    @property
    def issuers_crls_dir(self) -> Path:
        return self._issuers_crls

    @property
    def rejected_dir(self) -> Path:
        return self._rejected

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    @staticmethod
    def _clear_dir(directory: Path) -> None:
        for f in directory.iterdir():
            if f.is_file():
                f.unlink()

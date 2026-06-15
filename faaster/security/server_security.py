"""
Configuração de segurança standalone do servidor OPC UA.

Responsabilidades:
    - Bootstrap do PKI (cert auto-assinado na primeira inicialização)
    - Carregamento de certificado + chave privada no asyncua Server
    - Mapeamento de política/modo CLI → SecurityPolicyType asyncua
    - Configuração do TrustStore para validação de certificados de clientes
    - Tarefa de auto-aceitação de clientes (dev only): move rejected/ → trusted/

Integração com asyncua:
    Requer asyncua[crypto] >= 1.1.8 e a biblioteca cryptography >= 44.

Uso típico em setup():

    store = CertificateStore(args.pki_dir)
    await configure_server_security(opcua_server, store, args)

    # em run(), se --auto-accept-clients:
    asyncio.create_task(auto_accept_task(store, trust_store, stop_event))
"""
from __future__ import annotations

import asyncio
from enum import Enum
from pathlib import Path

from asyncua import Server
from asyncua import ua

from faaster.log import get_logger

from .certificate_store import CertificateStore
from .crypto_utils import generate_self_signed_certificate

logger = get_logger(__name__)


# ------------------------------------------------------------------
# Enums para CLI
# ------------------------------------------------------------------

class SecurityPolicy(str, Enum):
    basic256 = "basic256"   # Basic256Sha256
    aes128   = "aes128"     # Aes128_Sha256_RsaOaep
    aes256   = "aes256"     # Aes256_Sha256_RsaPss

    def __str__(self) -> str:
        return self.value


class SecurityMode(str, Enum):
    sign               = "sign"
    sign_and_encrypt   = "sign-and-encrypt"

    def __str__(self) -> str:
        return self.value


# ------------------------------------------------------------------
# Mapeamento política + modo → SecurityPolicyType asyncua
# ------------------------------------------------------------------

_POLICY_TYPE_MAP: dict[tuple[SecurityPolicy, SecurityMode], ua.SecurityPolicyType] = {
    (SecurityPolicy.basic256, SecurityMode.sign):           ua.SecurityPolicyType.Basic256Sha256_Sign,
    (SecurityPolicy.basic256, SecurityMode.sign_and_encrypt): ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt,
    (SecurityPolicy.aes128,   SecurityMode.sign):             ua.SecurityPolicyType.Aes128Sha256RsaOaep_Sign,
    (SecurityPolicy.aes128,   SecurityMode.sign_and_encrypt): ua.SecurityPolicyType.Aes128Sha256RsaOaep_SignAndEncrypt,
    (SecurityPolicy.aes256,   SecurityMode.sign):             ua.SecurityPolicyType.Aes256Sha256RsaPss_Sign,
    (SecurityPolicy.aes256,   SecurityMode.sign_and_encrypt): ua.SecurityPolicyType.Aes256Sha256RsaPss_SignAndEncrypt,
}


def build_security_policy_list(
    policies: list[SecurityPolicy] | None,
    mode: SecurityMode = SecurityMode.sign_and_encrypt,
    allow_anonymous: bool = False,
) -> list[ua.SecurityPolicyType]:
    """
    Converte as opções CLI em lista de SecurityPolicyType para asyncua.

    allow_anonymous=True adiciona NoSecurity ao início da lista, mantendo
    compatibilidade com clientes sem certificado (útil em dev/staging).
    """
    result: list[ua.SecurityPolicyType] = []

    if allow_anonymous or not policies:
        result.append(ua.SecurityPolicyType.NoSecurity)

    for policy in (policies or []):
        key = (policy, mode)
        if key not in _POLICY_TYPE_MAP:
            raise ValueError(f"Combinação não suportada: policy={policy}, mode={mode}")
        result.append(_POLICY_TYPE_MAP[key])

    return result


# ------------------------------------------------------------------
# Bootstrap do PKI
# ------------------------------------------------------------------

async def bootstrap_pki(
    store: CertificateStore,
    common_name: str,
    application_uri: str,
    san_dns: list[str] | None = None,
    san_ips: list[str] | None = None,
) -> None:
    """
    Gera um certificado auto-assinado + chave privada se o store estiver vazio.

    Idempotente: não sobrescreve certificados existentes.
    """
    if store.has_own_certificate():
        logger.info("server_security.pki_exists", path=str(store.own_cert_path))
        return

    logger.info(
        "server_security.generating_self_signed",
        common_name=common_name,
        application_uri=application_uri,
    )

    cert_der, key_pem = generate_self_signed_certificate(
        common_name=common_name,
        application_uri=application_uri,
        san_dns=san_dns,
        san_ips=san_ips,
    )

    store.save_own_certificate(cert_der)
    store.save_own_private_key(key_pem)

    logger.info("server_security.pki_bootstrapped")


# ------------------------------------------------------------------
# Configuração do servidor OPC UA
# ------------------------------------------------------------------

async def configure_server_security(
    opcua_server: Server,
    store: CertificateStore,
    policies: list[ua.SecurityPolicyType],
) -> object:
    """
    Aplica a configuração de segurança ao asyncua Server.

    Deve ser chamado APÓS server.init() e ANTES de iniciar o servidor
    (antes do `async with server:`).

    Retorna o TrustStore configurado para ser passado a auto_accept_task
    se --auto-accept-clients estiver ativado.
    """
    from asyncua.crypto.truststore import TrustStore

    # 1. Políticas de segurança
    opcua_server.set_security_policy(policies)
    logger.info("server_security.policies_set", policies=[str(p) for p in policies])

    # 2. Certificado e chave privada do servidor
    await opcua_server.load_certificate(str(store.own_cert_path))
    await opcua_server.load_private_key(str(store.own_key_path))
    logger.info("server_security.certificate_loaded", cert=str(store.own_cert_path))

    # 3. TrustStore — valida certificados de clientes entrantes
    #    rejected_dir recebe automaticamente certs não reconhecidos
    trust_store = TrustStore(
        trusted=[store.trusted_certs_dir, store.issuers_certs_dir],
        rejected=store.rejected_dir,
    )
    await trust_store.load()

    opcua_server.set_certificate_validator(trust_store)
    logger.info(
        "server_security.trust_store_loaded",
        trusted_dir=str(store.trusted_certs_dir),
        rejected_dir=str(store.rejected_dir),
    )

    return trust_store


# ------------------------------------------------------------------
# Auto-accept de clientes (dev only)
# ------------------------------------------------------------------

_AUTO_ACCEPT_INTERVAL = 5.0  # segundos entre varreduras

async def auto_accept_task(
    store: CertificateStore,
    trust_store: object,
    stop_event: asyncio.Event,
    interval: float = _AUTO_ACCEPT_INTERVAL,
) -> None:
    """
    Tarefa de desenvolvimento: move certificados de clientes de rejected/ para
    trusted/ automaticamente, dispensando aprovação manual.

    ATENÇÃO: Usar apenas em ambientes de desenvolvimento/teste. Em produção,
    certificados de clientes devem ser aprovados manualmente por um administrador.

    Workflow:
        1. Varre pki/rejected/ periodicamente
        2. Move cada .der encontrado para pki/trusted/certs/
        3. Recarrega o TrustStore para que conexões subsequentes sejam aceitas
    """
    logger.warning(
        "server_security.auto_accept_enabled",
        reason="ATENÇÃO: --auto-accept-clients ativado — qualquer cliente será confiado automaticamente",
    )

    while not stop_event.is_set():
        moved = _accept_pending(store)

        if moved:
            await trust_store.load()
            logger.info(
                "server_security.auto_accepted",
                count=moved,
                reason="cliente(s) auto-confiados; reconecte os clientes para usar a sessão segura",
            )

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


def _accept_pending(store: CertificateStore) -> int:
    """Move certs de rejected/ para trusted/certs/ e retorna a quantidade movida."""
    moved = 0
    for cert_file in store.rejected_dir.iterdir():
        if cert_file.suffix in (".der", ".pem", ".crt"):
            dest = store.trusted_certs_dir / cert_file.name
            cert_file.rename(dest)
            logger.info(
                "server_security.cert_accepted",
                cert=cert_file.name,
                dest=str(dest),
            )
            moved += 1
    return moved

"""
Certificate Manager — Pull Management workflow (OPC 10000-12 §7.9).

Orquestra o ciclo completo de gerenciamento de certificados via GDS:

    1. Bootstrap   — gera certificado auto-assinado se não existe nenhum
    2. Setup       — consulta grupos, verifica status, emite/renova via GDS, aplica TrustList
    3. Run         — loop de renovação periódica até stop_event ser sinalizado

Workflow Pull Management (Figura 13, OPC 10000-12):

    GetCertificateGroups(applicationId)
        └─ GetCertificateStatus(appId, groupId, typeId)
                └─ [se updateRequired]
                        StartSigningRequest(appId, groupId, typeId, csr)  ← chave local
                            └─ FinishRequest(appId, requestId)  ← polling Bad_NothingToDo
                                    └─ Salva cert + issuer chains
                └─ GetTrustList(appId, groupId) → NodeId
                        └─ read_trust_list(nodeId) → TrustListDataType
                                └─ CertificateStore.apply_trust_list(...)
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from asyncua import ua

from faaster.log import get_logger
from faaster.gds.certificate_client import GDSCertificateClient
from faaster.gds.models import ApplicationRecord

from .certificate_store import CertificateStore
from .crypto_utils import (
    generate_self_signed_certificate,
    generate_csr,
    load_private_key,
)

logger = get_logger(__name__)

# NodeId padrão para o DefaultApplicationGroup (OPC 10000-12 §7.7.4)
_DEFAULT_APP_GROUP = ua.NodeId(615, 0)
# NodeId padrão para RsaSha256ApplicationCertificateType (OPC 10000-12 §7.7.5)
_RSA_SHA256_CERT_TYPE = ua.NodeId(12560, 0)


class CertificateManager:
    """
    Gerencia o ciclo de vida de certificados OPC UA via GDS Pull Management.

    Parâmetros:
        gds_client       — GDSCertificateClient conectado ao servidor GDS
        store            — CertificateStore com o diretório pki/
        record           — ApplicationRecord já registrado no GDS
        common_name      — CN do certificado (ex: "Faaster AAS Server")
        application_uri  — URI da aplicação (ex: "urn:company:asset:aas")
        san_dns          — lista de DNS SANs (ex: ["myserver.local"])
        san_ips          — lista de IP SANs (ex: ["192.168.1.10"])
        renew_before_days— quantos dias antes do vencimento iniciar renovação
        poll_interval    — segundos de polling do FinishRequest
        poll_max         — máximo de tentativas no polling
    """

    def __init__(
        self,
        gds_client: GDSCertificateClient,
        store: CertificateStore,
        record: ApplicationRecord,
        common_name: str,
        application_uri: str,
        san_dns: list[str] | None = None,
        san_ips: list[str] | None = None,
        renew_before_days: int = 30,
        poll_interval: float = 5.0,
        poll_max: int = 60,
    ) -> None:
        self._gds = gds_client
        self._store = store
        self._record = record
        self._common_name = common_name
        self._application_uri = application_uri
        self._san_dns = san_dns or []
        self._san_ips = san_ips or []
        self._renew_before_days = renew_before_days
        self._poll_interval = poll_interval
        self._poll_max = poll_max

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    async def setup(self) -> None:
        """
        Executa o workflow completo de setup de certificado:

        1. Bootstrap: emite certificado auto-assinado se necessário (sem GDS)
        2. Abre sessão GDS e consulta grupos disponíveis
        3. Para cada grupo: verifica status → emite/renova se necessário
        4. Baixa e aplica a TrustList do grupo
        """
        await self._bootstrap_if_needed()

        if self._record.application_id is None:
            logger.warning(
                "certificate_manager.no_application_id",
                reason="application não registrada no GDS, pulando setup de certificado GDS",
            )
            return

        async with self._gds:
            app_id = self._record.application_id

            groups = await self._gds.get_certificate_groups(app_id)
            if not groups:
                logger.warning("certificate_manager.no_groups", application_id=str(app_id))
                return

            for group_id in groups:
                await self._setup_group(app_id, group_id)

    async def run(self, stop_event: asyncio.Event, renew_interval: float = 3600.0) -> None:
        """
        Loop de renovação periódica.

        Executa setup() no início e repete a cada renew_interval segundos ou
        quando o stop_event for sinalizado (encerrando o loop).
        """
        await self.setup()

        while True:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=renew_interval)
                break  # stop_event foi sinalizado
            except asyncio.TimeoutError:
                logger.info("certificate_manager.renewing")
                try:
                    await self.setup()
                except Exception:
                    logger.exception("certificate_manager.renewal_failed")

        logger.info("certificate_manager.stopped")

    # ------------------------------------------------------------------
    # Setup por grupo de certificado
    # ------------------------------------------------------------------

    async def _setup_group(self, app_id: ua.NodeId, group_id: ua.NodeId) -> None:
        cert_type_id = _RSA_SHA256_CERT_TYPE

        try:
            update_required = await self._gds.get_certificate_status(
                app_id, group_id, cert_type_id
            )
        except Exception:
            logger.warning(
                "certificate_manager.status_check_failed",
                group_id=str(group_id),
            )
            update_required = True  # conservador: tenta renovar se não conseguiu verificar

        if update_required:
            await self._issue_certificate(app_id, group_id, cert_type_id)

        await self._apply_trust_list(app_id, group_id)

    async def _issue_certificate(
        self,
        app_id: ua.NodeId,
        group_id: ua.NodeId,
        cert_type_id: ua.NodeId,
    ) -> None:
        """
        Emite ou renova o certificado via StartSigningRequest + FinishRequest.

        A chave privada é gerada/mantida localmente; o GDS recebe apenas o CSR.
        """
        key_pem = self._store.load_own_private_key()
        if key_pem is None:
            # Gera novo par de chaves — a chave privada fica armazenada localmente
            _, key_pem = generate_self_signed_certificate(
                common_name=self._common_name,
                application_uri=self._application_uri,
                san_dns=self._san_dns,
                san_ips=self._san_ips,
            )
            self._store.save_own_private_key(key_pem)

        csr_der = generate_csr(
            key_pem=key_pem,
            common_name=self._common_name,
            application_uri=self._application_uri,
            san_dns=self._san_dns,
            san_ips=self._san_ips,
        )

        request_id = await self._gds.start_signing_request(
            app_id, group_id, cert_type_id, csr_der
        )

        certificate, _private_key, issuers = await self._gds.finish_request(
            app_id,
            request_id,
            poll_interval=self._poll_interval,
            max_attempts=self._poll_max,
        )

        if not certificate:
            raise RuntimeError("GDS retornou certificado vazio após FinishRequest.")

        self._store.save_own_certificate(certificate)

        for i, issuer_cert in enumerate(issuers):
            self._store.save_issuer_certificate(issuer_cert, f"gds_issuer_{i:04d}.der")

        logger.info(
            "certificate_manager.certificate_issued",
            group_id=str(group_id),
            issuer_count=len(issuers),
        )

    async def _apply_trust_list(self, app_id: ua.NodeId, group_id: ua.NodeId) -> None:
        """Baixa e aplica a TrustList do grupo ao store local."""
        try:
            trust_list_node_id = await self._gds.get_trust_list(app_id, group_id)
            trust_list = await self._gds.read_trust_list(trust_list_node_id)
            self._store.apply_trust_list(trust_list)
        except Exception:
            logger.exception(
                "certificate_manager.trust_list_failed",
                group_id=str(group_id),
            )

    # ------------------------------------------------------------------
    # Bootstrap — certificado auto-assinado para conexão inicial ao GDS
    # ------------------------------------------------------------------

    async def _bootstrap_if_needed(self) -> None:
        """
        Gera um certificado auto-assinado se o store estiver vazio.

        Necessário para a conexão inicial ao GDS (canal SignAndEncrypt exige
        um certificado mesmo que seja auto-assinado).
        """
        if self._store.has_own_certificate():
            return

        logger.info(
            "certificate_manager.bootstrap",
            reason="nenhum certificado encontrado, gerando auto-assinado",
        )

        cert_der, key_pem = generate_self_signed_certificate(
            common_name=self._common_name,
            application_uri=self._application_uri,
            san_dns=self._san_dns,
            san_ips=self._san_ips,
        )

        self._store.save_own_certificate(cert_der)
        self._store.save_own_private_key(key_pem)

        logger.info("certificate_manager.bootstrap_complete")

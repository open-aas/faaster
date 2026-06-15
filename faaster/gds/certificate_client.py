"""
GDS Certificate Client — OPC 10000-12 §7.9 (CertificateDirectoryType Methods).

Estende GDSClient com os métodos de gerenciamento de certificados expostos pelo
CertificateManager (que na prática é o mesmo servidor GDS).

Métodos implementados:

    GetCertificateGroups     §7.9.7  — grupos de certificados disponíveis
    GetCertificateStatus     §7.9.10 — verifica se o certificado precisa ser renovado
    StartSigningRequest      §7.9.3  — submete CSR externo para assinatura pela CA
    StartNewKeyPairRequest   §7.9.4  — solicita geração de novo par chave+cert pelo GDS
    FinishRequest            §7.9.5  — polling até a CA assinar (retorna cert + chave)
    GetCertificates          §7.9.8  — retorna certificados atuais da aplicação
    GetTrustList             §7.9.9  — retorna NodeId do objeto TrustList do grupo
    RevokeCertificate        §7.9.6  — revoga um certificado emitido

TrustList:

    read_trust_list          — lê o TrustListDataType via FileType (OpenWithMasks + Read)

Todos os métodos requerem canal SignAndEncrypt e credenciais com
ApplicationSelfAdmin Privilege ou DiscoveryAdmin Role (§7.2, §6.2).
"""
from __future__ import annotations

import asyncio

from asyncua import ua
from asyncua.ua import NodeId

from faaster.log import get_logger

from .client import GDSClient

logger = get_logger(__name__)

# Polling para FinishRequest enquanto a CA processa a solicitação
_FINISH_POLL_INTERVAL = 5.0   # segundos entre tentativas
_FINISH_MAX_ATTEMPTS = 60     # máximo de 5 minutos de espera


class GDSCertificateClient(GDSClient):
    """
    Cliente GDS com suporte a gerenciamento de certificados (Pull Management).

    Uso:
        async with GDSCertificateClient(url, username, password) as gds:
            groups = await gds.get_certificate_groups(application_id)
            needs_update = await gds.get_certificate_status(app_id, group_id, type_id)
            if needs_update:
                request_id = await gds.start_signing_request(app_id, group_id, type_id, csr)
                cert, key, issuers = await gds.finish_request(app_id, request_id)
            trust_list_id = await gds.get_trust_list(app_id, group_id)
            trust_list = await gds.read_trust_list(trust_list_id)
    """

    # ------------------------------------------------------------------
    # §7.9.7  GetCertificateGroups
    # ------------------------------------------------------------------

    async def get_certificate_groups(self, application_id: NodeId) -> list[NodeId]:
        """
        Retorna os NodeIds dos CertificateGroups disponíveis para a aplicação.

        O primeiro elemento é normalmente o DefaultApplicationGroup.

        OPC 10000-12 §7.9.7
        """
        result = await self._directory.call_method(
            f"{self._ns}:GetCertificateGroups",
            application_id,
        )
        if result is None:
            return []
        return list(result) if isinstance(result, (list, tuple)) else [result]

    # ------------------------------------------------------------------
    # §7.9.10  GetCertificateStatus
    # ------------------------------------------------------------------

    async def get_certificate_status(
        self,
        application_id: NodeId,
        certificate_group_id: NodeId,
        certificate_type_id: NodeId,
    ) -> bool:
        """
        Verifica se o certificado atual precisa ser renovado.

        Retorna True se uma atualização é necessária.

        OPC 10000-12 §7.9.10
        """
        update_required: bool = await self._directory.call_method(
            f"{self._ns}:GetCertificateStatus",
            application_id,
            certificate_group_id,
            certificate_type_id,
        )
        logger.info(
            "gds_cert_client.certificate_status",
            application_id=str(application_id),
            update_required=update_required,
        )
        return bool(update_required)

    # ------------------------------------------------------------------
    # §7.9.3  StartSigningRequest
    # ------------------------------------------------------------------

    async def start_signing_request(
        self,
        application_id: NodeId,
        certificate_group_id: NodeId,
        certificate_type_id: NodeId,
        certificate_request: bytes,
    ) -> NodeId:
        """
        Submete um CSR (PKCS#10, DER) ao GDS para assinatura pela CA.

        O par de chaves é gerado localmente pelo servidor — o GDS recebe
        apenas a requisição de assinatura, nunca a chave privada.

        Retorna o requestId para polling via FinishRequest.

        OPC 10000-12 §7.9.3
        """
        request_id: NodeId = await self._directory.call_method(
            f"{self._ns}:StartSigningRequest",
            application_id,
            certificate_group_id,
            certificate_type_id,
            ua.ByteString(certificate_request),
        )
        logger.info(
            "gds_cert_client.signing_request_started",
            request_id=str(request_id),
        )
        return request_id

    # ------------------------------------------------------------------
    # §7.9.4  StartNewKeyPairRequest
    # ------------------------------------------------------------------

    async def start_new_key_pair_request(
        self,
        application_id: NodeId,
        certificate_group_id: NodeId,
        certificate_type_id: NodeId,
        subject_name: str,
        domain_names: list[str],
        private_key_format: str = "PEM",
        private_key_password: str = "",
    ) -> NodeId:
        """
        Solicita ao GDS a geração de um novo par de chaves + certificado.

        Usar quando o dispositivo não tem capacidade de gerar chaves RSA
        localmente (ex: hardware constrained). Para dispositivos normais,
        prefira StartSigningRequest que mantém a chave privada local.

        private_key_format: "PEM" ou "PFX" (PKCS#12).

        OPC 10000-12 §7.9.4
        """
        request_id: NodeId = await self._directory.call_method(
            f"{self._ns}:StartNewKeyPairRequest",
            application_id,
            certificate_group_id,
            certificate_type_id,
            subject_name,
            domain_names,
            private_key_format,
            private_key_password,
        )
        logger.info(
            "gds_cert_client.new_key_pair_request_started",
            request_id=str(request_id),
        )
        return request_id

    # ------------------------------------------------------------------
    # §7.9.5  FinishRequest  (com polling automático)
    # ------------------------------------------------------------------

    async def finish_request(
        self,
        application_id: NodeId,
        request_id: NodeId,
        poll_interval: float = _FINISH_POLL_INTERVAL,
        max_attempts: int = _FINISH_MAX_ATTEMPTS,
    ) -> tuple[bytes, bytes, list[bytes]]:
        """
        Aguarda a conclusão de um StartSigningRequest ou StartNewKeyPairRequest.

        Enquanto a CA ainda está processando, o GDS retorna Bad_NothingToDo.
        Este método faz o polling automaticamente até receber a resposta ou
        exceder max_attempts.

        Retorna:
            (certificate: bytes, private_key: bytes, issuer_certificates: list[bytes])

            private_key estará vazio se a requisição foi feita via StartSigningRequest
            (a chave privada já existe localmente).

        OPC 10000-12 §7.9.5
        """
        for attempt in range(1, max_attempts + 1):
            try:
                result = await self._directory.call_method(
                    f"{self._ns}:FinishRequest",
                    application_id,
                    request_id,
                )
                # result = (certificate, privateKey, issuerCertificates[])
                certificate = bytes(result[0]) if result[0] else b""
                private_key = bytes(result[1]) if result[1] else b""
                issuers = [bytes(c) for c in (result[2] or [])]

                logger.info(
                    "gds_cert_client.finish_request_done",
                    attempt=attempt,
                    cert_size=len(certificate),
                    issuer_count=len(issuers),
                )
                return certificate, private_key, issuers

            except ua.uaerrors.BadNothingToDo:
                logger.info(
                    "gds_cert_client.finish_request_pending",
                    attempt=attempt,
                    max_attempts=max_attempts,
                )
                if attempt < max_attempts:
                    await asyncio.sleep(poll_interval)

        raise TimeoutError(
            f"GDS não concluiu o processamento do certificado após "
            f"{max_attempts} tentativas ({max_attempts * poll_interval:.0f}s)."
        )

    # ------------------------------------------------------------------
    # §7.9.8  GetCertificates
    # ------------------------------------------------------------------

    async def get_certificates(
        self,
        application_id: NodeId,
        certificate_group_id: NodeId,
    ) -> tuple[list[NodeId], list[bytes]]:
        """
        Retorna os certificados atualmente associados à aplicação no grupo.

        Retorna:
            (certificateTypeIds[], certificates[])

        OPC 10000-12 §7.9.8
        """
        result = await self._directory.call_method(
            f"{self._ns}:GetCertificates",
            application_id,
            certificate_group_id,
        )
        type_ids = list(result[0] or [])
        certs = [bytes(c) for c in (result[1] or [])]
        return type_ids, certs

    # ------------------------------------------------------------------
    # §7.9.6  RevokeCertificate
    # ------------------------------------------------------------------

    async def revoke_certificate(
        self,
        application_id: NodeId,
        certificate: bytes,
    ) -> None:
        """
        Revoga um certificado emitido pelo GDS.

        OPC 10000-12 §7.9.6
        """
        await self._directory.call_method(
            f"{self._ns}:RevokeCertificate",
            application_id,
            ua.ByteString(certificate),
        )
        logger.info("gds_cert_client.certificate_revoked")

    # ------------------------------------------------------------------
    # §7.9.9  GetTrustList  +  leitura via FileType
    # ------------------------------------------------------------------

    async def get_trust_list(
        self,
        application_id: NodeId,
        certificate_group_id: NodeId,
    ) -> NodeId:
        """
        Retorna o NodeId do objeto TrustList associado ao grupo de certificados.

        OPC 10000-12 §7.9.9
        """
        trust_list_id: NodeId = await self._directory.call_method(
            f"{self._ns}:GetTrustList",
            application_id,
            certificate_group_id,
        )
        return trust_list_id

    async def read_trust_list(self, trust_list_node_id: NodeId) -> object:
        """
        Lê o TrustListDataType completo via FileType (OPC 10000-12 §7.8.2).

        Workflow:
            1. OpenWithMasks(ALL_LISTS=0x0F)  → fileHandle
            2. Lê o atributo Size              → tamanho em bytes
            3. Read(fileHandle, size)          → bytes brutos
            4. Close(fileHandle)
            5. Deserializa como TrustListDataType (ua_binary)

        OPC 10000-12 §7.8.2 / Tabelas 28–29
        """
        trust_list_node = self._client.get_node(trust_list_node_id)

        # 1. OpenWithMasks — abre para leitura de todas as listas
        file_handle: ua.UInt32 = await trust_list_node.call_method(
            f"{self._ns}:OpenWithMasks",
            ua.UInt32(0x0F),  # ALL_LISTS
        )

        raw_bytes = b""
        try:
            # 2. Lê o atributo Size para saber quantos bytes ler
            size_node = await trust_list_node.get_child("0:Size")
            size: int = await size_node.read_value()

            # 3. Read(fileHandle, length)
            raw_bytes = await trust_list_node.call_method(
                "0:Read",
                file_handle,
                ua.Int32(size),
            )
            raw_bytes = bytes(raw_bytes) if raw_bytes else b""

        finally:
            # 4. Close — sempre fecha, mesmo em caso de erro
            await trust_list_node.call_method("0:Close", file_handle)

        # 5. Deserializa TrustListDataType (tipo padrão OPC UA, namespace 0)
        trust_list = _decode_trust_list(raw_bytes)

        logger.info(
            "gds_cert_client.trust_list_read",
            trusted_certs=len(trust_list.TrustedCertificates or []),
            issuer_certs=len(trust_list.IssuerCertificates or []),
        )
        return trust_list


# ------------------------------------------------------------------
# Deserialização do TrustListDataType
# ------------------------------------------------------------------

def _decode_trust_list(raw: bytes) -> object:
    """
    Decodifica bytes OPC UA binários como TrustListDataType.

    TrustListDataType é um tipo padrão OPC UA (namespace 0) e está
    disponível em asyncua após load_type_definitions().
    """
    from asyncua.ua import ua_binary, Buffer

    trust_list_type = getattr(ua, "TrustListDataType", None)

    if trust_list_type is None:
        raise RuntimeError(
            "ua.TrustListDataType não disponível. "
            "Verifique se load_type_definitions() foi chamado após connect()."
        )

    buf = Buffer(raw)
    return ua_binary.struct_from_binary(trust_list_type, buf)

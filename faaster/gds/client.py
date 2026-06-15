"""
GDS Client — OPC 10000-12 §6.5  (DirectoryType Methods).

Implementa os seis métodos do DirectoryType que um servidor OPC UA deve chamar
para se registrar e consultar o Global Discovery Server:

    FindApplications      §6.5.4
    RegisterApplication   §6.5.6
    UpdateApplication     §6.5.7
    UnregisterApplication §6.5.8
    GetApplication        §6.5.9
    QueryApplications     §6.5.10

A conexão utiliza asyncua.Client. Após connect(), os tipos da namespace GDS são
carregados via load_type_definitions() para que ApplicationRecordDataType fique
disponível como ua.ApplicationRecordDataType.
"""
from __future__ import annotations

from asyncua import Client, Node
from asyncua import ua
from asyncua.ua import ApplicationType, LocalizedText, NodeId

from faaster.log import get_logger

from .models import ApplicationRecord

logger = get_logger(__name__)

_GDS_NS_URI = "http://opcfoundation.org/UA/GDS/"


class GDSClient:
    """
    Cliente OPC UA para o Global Discovery Server.

    Uso como context manager assíncrono:

        async with GDSClient("opc.tcp://gds:58810") as gds:
            apps = await gds.find_applications("urn:my:server")
    """

    def __init__(
        self,
        url: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._url = url
        self._username = username
        self._password = password
        self._client: Client | None = None
        self._directory: Node | None = None
        self._ns: int = 0

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    async def __aenter__(self) -> GDSClient:
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        """Conecta ao GDS e carrega os tipos da namespace GDS."""
        self._client = Client(self._url)

        if self._username:
            self._client.set_user(self._username)
            self._client.set_password(self._password)

        await self._client.connect()

        # Carrega ApplicationRecordDataType e demais structs da namespace GDS
        await self._client.load_type_definitions()

        self._ns = await self._client.get_namespace_index(_GDS_NS_URI)
        self._directory = await self._resolve_directory()

        logger.info("gds_client.connected", url=self._url, ns=self._ns)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.disconnect()
            self._client = None
            self._directory = None
        logger.info("gds_client.disconnected")

    # ------------------------------------------------------------------
    # §6.5.4  FindApplications
    # ------------------------------------------------------------------

    async def find_applications(self, application_uri: str) -> list[ApplicationRecord]:
        """
        Retorna os registros associados ao applicationUri.

        Array vazio → aplicação não registrada no GDS.
        Array de tamanho 1 → registro encontrado.
        Array > 1 → erro fatal, requer intervenção de DiscoveryAdmin.

        OPC 10000-12 §6.5.4
        """
        raw = await self._directory.call_method(
            f"{self._ns}:FindApplications",
            application_uri,
        )

        if raw is None:
            return []
        records = raw if isinstance(raw, (list, tuple)) else [raw]
        return [self._from_ua(r) for r in records]

    # ------------------------------------------------------------------
    # §6.5.6  RegisterApplication
    # ------------------------------------------------------------------

    async def register_application(self, record: ApplicationRecord) -> NodeId:
        """
        Registra uma nova aplicação no GDS e retorna o applicationId.

        Requer DiscoveryAdmin Role ou ApplicationAdmin Privilege.
        Retorna Bad_EntryExists se o applicationUri já estiver registrado.

        OPC 10000-12 §6.5.6
        """
        application_id: NodeId = await self._directory.call_method(
            f"{self._ns}:RegisterApplication",
            self._to_ua(record),
        )
        logger.info(
            "gds_client.registered",
            uri=record.application_uri,
            application_id=str(application_id),
        )
        return application_id

    # ------------------------------------------------------------------
    # §6.5.7  UpdateApplication
    # ------------------------------------------------------------------

    async def update_application(self, record: ApplicationRecord) -> None:
        """
        Atualiza o registro existente de uma aplicação no GDS.

        O applicationUri não pode ser alterado (retorna Bad_WriteNotSupported).
        Requer DiscoveryAdmin Role, ApplicationSelfAdmin ou ApplicationAdmin.

        OPC 10000-12 §6.5.7
        """
        await self._directory.call_method(
            f"{self._ns}:UpdateApplication",
            self._to_ua(record),
        )
        logger.info("gds_client.updated", uri=record.application_uri)

    # ------------------------------------------------------------------
    # §6.5.8  UnregisterApplication
    # ------------------------------------------------------------------

    async def unregister_application(self, application_id: NodeId) -> None:
        """
        Remove o registro de uma aplicação do GDS.

        Se a aplicação possuir certificados emitidos pelo CertificateManager,
        estes serão revogados automaticamente.

        OPC 10000-12 §6.5.8
        """
        await self._directory.call_method(
            f"{self._ns}:UnregisterApplication",
            application_id,
        )
        logger.info("gds_client.unregistered", application_id=str(application_id))

    # ------------------------------------------------------------------
    # §6.5.9  GetApplication
    # ------------------------------------------------------------------

    async def get_application(self, application_id: NodeId) -> ApplicationRecord:
        """
        Retorna o registro de uma aplicação a partir do seu applicationId.

        OPC 10000-12 §6.5.9
        """
        raw = await self._directory.call_method(
            f"{self._ns}:GetApplication",
            application_id,
        )
        return self._from_ua(raw)

    # ------------------------------------------------------------------
    # §6.5.10  QueryApplications
    # ------------------------------------------------------------------

    async def query_applications(
        self,
        starting_record_id: int = 0,
        max_records_to_return: int = 0,
        application_name: str = "",
        application_uri: str = "",
        application_type: int = 0,
        product_uri: str = "",
        capabilities: list[str] | None = None,
    ) -> tuple[object, int, list]:
        """
        Consulta aplicações registradas no GDS com filtros combinados (AND).

        Parâmetros de entrada (OPC 10000-12 §6.5.10):
            starting_record_id    — Retorna apenas registros com id > este valor.
                                    0 = início.
            max_records_to_return — Limite de resultados. 0 = sem limite.
            application_name      — Filtro LIKE no nome padrão da aplicação.
            application_uri       — Filtro LIKE no applicationUri.
            application_type      — Máscara de tipo: 0=todos, 0x1=Server, 0x2=Client.
            product_uri           — Filtro LIKE no productUri.
            capabilities          — Lista de CapabilityIdentifiers que a aplicação
                                    deve suportar (todos os fornecidos).

        Retorno:
            (lastCounterResetTime, nextRecordId, applications[])
            nextRecordId == 0 → não há mais registros.
        """
        results = await self._directory.call_method(
            f"{self._ns}:QueryApplications",
            ua.UInt32(starting_record_id),
            ua.UInt32(max_records_to_return),
            application_name,
            application_uri,
            ua.UInt32(application_type),
            product_uri,
            capabilities or [],
        )
        # results = (lastCounterResetTime, nextRecordId, ApplicationDescription[])
        return results

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    async def _resolve_directory(self) -> Node:
        """Navega o Objects folder para encontrar o nó Directory do GDS."""
        objects = self._client.get_objects_node()
        for child in await objects.get_children():
            bn = await child.read_browse_name()
            if bn.Name == "Directory":
                return child
        raise RuntimeError(
            f"Nó 'Directory' não encontrado no GDS em {self._url}. "
            "Verifique se a URL aponta para um GlobalDiscoveryServer válido."
        )

    def _to_ua(self, record: ApplicationRecord) -> object:
        """Converte ApplicationRecord → ApplicationRecordDataType OPC UA."""
        t = getattr(ua, "ApplicationRecordDataType")
        obj = t()
        obj.ApplicationId = record.application_id or NodeId()
        obj.ApplicationUri = record.application_uri
        obj.ApplicationType = record.application_type
        obj.ApplicationNames = record.application_names
        obj.ProductUri = record.product_uri
        obj.DiscoveryUrls = record.discovery_urls
        obj.ServerCapabilities = record.server_capabilities
        return obj

    def _from_ua(self, obj: object) -> ApplicationRecord:
        """Converte ApplicationRecordDataType OPC UA → ApplicationRecord."""
        return ApplicationRecord(
            application_id=obj.ApplicationId,
            application_uri=obj.ApplicationUri,
            application_type=obj.ApplicationType,
            application_names=list(obj.ApplicationNames),
            product_uri=obj.ProductUri,
            discovery_urls=list(obj.DiscoveryUrls),
            server_capabilities=list(obj.ServerCapabilities),
        )

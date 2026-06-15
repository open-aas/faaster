"""ApplicationRecordDataType — OPC 10000-12 §6.5.5."""
from __future__ import annotations

from dataclasses import dataclass, field

from asyncua.ua import ApplicationType, LocalizedText, NodeId


@dataclass
class ApplicationRecord:
    """
    Mapeamento Python do ApplicationRecordDataType (OPC 10000-12 §6.5.5, Tabela 7).

    application_id      — NodeId atribuído pelo GDS após RegisterApplication;
                          None antes do primeiro registro.
    application_uri     — URI único e global da aplicação OPC UA.
    application_type    — Server | Client | ClientAndServer | DiscoveryServer.
    application_names   — Lista de nomes localizados; o primeiro elemento é o
                          nome padrão (ApplicationDescription.applicationName).
    product_uri         — URI global do produto, atribuído pelo fabricante.
    discovery_urls      — Lista de DiscoveryUrls expostas pela aplicação.
                          A primeira URL HTTPS define o Common Name do certificado.
                          URLs com prefixo "rcp+" indicam suporte a reverse connect.
    server_capabilities — CapabilityIdentifiers (valores válidos em Annex D).
                          Deve incluir "NA" para aplicações non-OPC UA.
    """

    application_uri: str
    application_type: ApplicationType
    application_names: list[LocalizedText]
    product_uri: str
    discovery_urls: list[str]
    server_capabilities: list[str] = field(default_factory=list)
    application_id: NodeId | None = None

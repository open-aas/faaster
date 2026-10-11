"""
Leitura dos submodelos AID (IDTA 02017) e AIMC (IDTA 02027) a partir do
documento JSON original do AAS — sem depender dos nós OPC UA, já que o
parser ainda não cria nós para SubmodelElementList.

Os submodelos são encontrados pelo semanticId, nunca pelo idShort.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs

import re

from faaster.log import get_logger


logger = get_logger(__name__)

AID_SEMANTIC_PREFIX = "https://admin-shell.io/idta/AssetInterfacesDescription/"
AIMC_SEMANTIC_PREFIX = "https://admin-shell.io/idta/AssetInterfacesMappingConfiguration/"

# forma textual de um NodeId OPC UA: [ns=<n>;]{i,s,g,b}=<id>
_NODE_ID = re.compile(r"^(ns=\d+;)?[isgb]=.+")


# -----------------------------------------------------------------------------
# Utilidades sobre o documento
# -----------------------------------------------------------------------------

def semantic_id(element: Dict[str, Any]) -> str:
    keys = (element.get("semanticId") or {}).get("keys") or []
    return keys[0].get("value", "") if keys else ""


def children(element: Dict[str, Any]) -> List[Dict[str, Any]]:
    value = element.get("value")
    if isinstance(value, list):
        return value
    return element.get("submodelElements") or []


def child(element: Dict[str, Any], id_short: str) -> Optional[Dict[str, Any]]:
    for c in children(element):
        if c.get("idShort") == id_short:
            return c
    return None


def child_value(element: Dict[str, Any], id_short: str) -> Optional[str]:
    c = child(element, id_short)
    return c.get("value") if c is not None else None


def submodel_version(semantic: str, prefix: str) -> Tuple[int, ...]:
    """'…/AssetInterfacesDescription/1/2/Submodel' → (1, 2)."""
    parts = semantic[len(prefix):].split("/")
    return tuple(int(p) for p in parts if p.isdigit())


# -----------------------------------------------------------------------------
# AID
# -----------------------------------------------------------------------------

@dataclass
class PropertyAffordance:
    """Um ponto de dados do ativo (InteractionMetadata/properties/<nome>)."""
    name: str
    title: Optional[str] = None
    data_type: Optional[str] = None
    observable: bool = False
    href: Optional[str] = None
    browse_path: Optional[str] = None

    @property
    def node_id(self) -> Optional[str]:
        """NodeId do href no formato da ligação OPC UA ('?id=ns=3;s=…')."""
        if not self.href or "id=" not in self.href:
            return None
        query = self.href.split("?", 1)[-1]
        node_id = parse_qs(query).get("id", [None])[0]
        # ignora placeholders de ferramentas de geração ('?id=PENDENTE')
        if node_id and _NODE_ID.match(node_id):
            return node_id
        return None


@dataclass
class AssetInterface:
    """Uma interface do AID (ex.: InterfaceOPCUA)."""
    submodel_id: str
    id_short: str
    base: str
    content_type: Optional[str] = None
    security_schemes: List[str] = field(default_factory=list)
    properties: Dict[str, PropertyAffordance] = field(default_factory=dict)

    @property
    def scheme(self) -> str:
        """Esquema do endpoint — escolhe o driver ('opc.tcp', 'modbus+tcp', …)."""
        return self.base.split("://", 1)[0] if "://" in self.base else ""


def _security_schemes(endpoint: Dict[str, Any]) -> List[str]:
    """Esquemas referenciados em 'security' (lista de ReferenceElements)."""
    definitions = child(endpoint, "securityDefinitions") or {}
    security = child(endpoint, "security") or {}
    schemes = []
    for item in children(security):
        name = None
        if item.get("modelType") == "ReferenceElement":
            keys = (item.get("value") or {}).get("keys") or []
            name = keys[-1].get("value") if keys else None
        elif item.get("modelType") == "Property":
            # forma antiga (AID 1.0 de alguns modelos): Property com o nome do esquema
            name = item.get("value")
        definition = child(definitions, name) if name else None
        scheme = child_value(definition, "scheme") if definition else None
        if scheme:
            schemes.append(scheme)
    return schemes


def _property_affordance(element: Dict[str, Any]) -> PropertyAffordance:
    forms = child(element, "forms") or {}
    # AID 1.0 usava uma lista de forms (form0…); a 1.1+ usa uma coleção
    if forms.get("modelType") == "SubmodelElementList":
        forms = (children(forms) or [{}])[0]
    observable = (child_value(element, "observable") or "").lower() == "true"
    return PropertyAffordance(
        name=element["idShort"],
        title=child_value(element, "title"),
        data_type=child_value(element, "type"),
        observable=observable,
        href=child_value(forms, "href"),
        browse_path=child_value(forms, "uav_browsePath"),
    )


def parse_aid(submodel: Dict[str, Any]) -> List[AssetInterface]:
    interfaces = []
    for element in children(submodel):
        endpoint = child(element, "EndpointMetadata")
        if element.get("modelType") != "SubmodelElementCollection" or endpoint is None:
            continue
        base = child_value(endpoint, "base")
        if not base:
            logger.warning("binding.aid.no_base", submodel_id=submodel["id"], interface=element["idShort"])
            continue
        interface = AssetInterface(
            submodel_id=submodel["id"],
            id_short=element["idShort"],
            base=base,
            content_type=child_value(endpoint, "contentType"),
            security_schemes=_security_schemes(endpoint),
        )
        interaction = child(element, "InteractionMetadata") or {}
        for prop in children(child(interaction, "properties") or {}):
            if prop.get("idShort"):
                affordance = _property_affordance(prop)
                interface.properties[affordance.name] = affordance
        interfaces.append(interface)
    return interfaces


# -----------------------------------------------------------------------------
# AIMC
# -----------------------------------------------------------------------------

@dataclass
class MappingEndpoint:
    """Uma Source ou um Sink de uma MappingConfiguration."""
    keys: List[Tuple[str, str]]
    id: str
    polling_interval: Optional[float] = None


@dataclass
class MappingConfiguration:
    index: int
    sources: List[MappingEndpoint] = field(default_factory=list)
    sinks: List[MappingEndpoint] = field(default_factory=list)
    default_polling_interval: Optional[float] = None
    has_transformation: bool = False


def _reference_keys(element: Optional[Dict[str, Any]]) -> List[Tuple[str, str]]:
    keys = ((element or {}).get("value") or {}).get("keys") or []
    return [(k.get("type", ""), k.get("value", "")) for k in keys]


def _float(value: Optional[str]) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def _endpoints(items: Optional[Dict[str, Any]], ref: str, ident: str) -> List[MappingEndpoint]:
    endpoints = []
    for item in children(items or {}):
        endpoints.append(MappingEndpoint(
            keys=_reference_keys(child(item, ref)),
            id=child_value(item, ident) or "",
            polling_interval=_float(child_value(item, "PollingInterval")),
        ))
    return endpoints


def parse_aimc(submodel: Dict[str, Any]) -> List[MappingConfiguration]:
    configurations = []
    mapping_list = child(submodel, "MappingConfigurations") or {}
    for index, mc in enumerate(children(mapping_list)):
        transformation = child(mc, "Transformation")
        configurations.append(MappingConfiguration(
            index=index,
            sources=_endpoints(child(mc, "Sources"), "Source", "SourceId"),
            sinks=_endpoints(child(mc, "Sinks"), "Sink", "SinkId"),
            default_polling_interval=_float(child_value(mc, "DefaultPollingInterval")),
            has_transformation=bool(transformation and transformation.get("value")),
        ))
    return configurations


# -----------------------------------------------------------------------------
# Referências
# -----------------------------------------------------------------------------

def id_short_path(keys: List[Tuple[str, str]]) -> Optional[str]:
    """
    Chaves de uma ModelReference (a partir do Submodel) → idShortPath no
    formato da API ('Coll.Prop', 'List[0].Prop'). Índices de lista vêm como
    valor numérico da chave, como define o metamodelo.
    """
    path = ""
    for key_type, value in keys[1:]:
        if value.isdigit():
            path += f"[{value}]"
        else:
            path = f"{path}.{value}" if path else value
    return path or None

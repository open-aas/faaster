"""
Serialização das respostas da API HTTP/REST a partir do repositório.

Aplica, sobre uma cópia do elemento do modelo:
  - valores vivos lidos do address space OPC UA (AAS Tipo 2 reativo);
  - o modificador level (deep | core);
  - o modificador extent (withBlobValue | withoutBlobValue).

Ver IDTA-01002-3-2 §Operation Parameters.
"""
import base64
import copy
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from faaster.log import get_logger
from faaster.parser.node_registry import NodeRegistry

from .repository import CHILDREN_BY_ID_SHORT, CHILDREN_BY_INDEX, iter_children


logger = get_logger(__name__)


class Level(str, Enum):
    deep = "deep"
    core = "core"


class Extent(str, Enum):
    with_blob_value = "withBlobValue"
    without_blob_value = "withoutBlobValue"


def _children_key(element: Dict[str, Any]) -> Optional[str]:
    model_type = element.get("modelType")
    return CHILDREN_BY_ID_SHORT.get(model_type) or CHILDREN_BY_INDEX.get(model_type)


def format_xs_value(value: Any) -> Optional[str]:
    """
    Converte o valor lido do OPC UA para a forma léxica xsd usada no
    JSON da Part 1 (Property.value é sempre string).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(value).decode("ascii")
    return str(value)


class AASSerializer:
    def __init__(self, registry: Optional[NodeRegistry] = None) -> None:
        self._registry = registry

    async def submodel(
        self,
        submodel: Dict[str, Any],
        level: Level = Level.deep,
        extent: Extent = Extent.without_blob_value,
    ) -> Dict[str, Any]:
        result = {k: copy.deepcopy(v) for k, v in submodel.items() if k != "submodelElements"}

        elements = submodel.get("submodelElements")
        if elements:
            result["submodelElements"] = await self.submodel_elements(
                elements, submodel["id"], level, extent
            )

        return result

    async def submodel_elements(
        self,
        elements: List[Dict[str, Any]],
        submodel_id: str,
        level: Level = Level.deep,
        extent: Extent = Extent.without_blob_value,
    ) -> List[Dict[str, Any]]:
        """Elementos do topo de um submodelo — filhos diretos do nível requisitado."""
        return [
            await self._render(
                element,
                submodel_id=submodel_id,
                path=element.get("idShort", ""),
                depth=0,
                level=level,
                extent=extent,
            )
            for element in elements
        ]

    async def submodel_element(
        self,
        element: Dict[str, Any],
        submodel_id: str,
        path: str,
        level: Level = Level.deep,
        extent: Extent = Extent.without_blob_value,
    ) -> Dict[str, Any]:
        # o elemento pedido conta como "nível requisitado": em core os filhos
        # diretos vêm, mas sem os netos
        return await self._render(element, submodel_id, path, depth=-1, level=level, extent=extent)

    async def _render(
        self,
        element: Dict[str, Any],
        submodel_id: str,
        path: str,
        depth: int,
        level: Level,
        extent: Extent,
    ) -> Dict[str, Any]:
        """
        depth = distância até o elemento requisitado (-1 = ele mesmo,
        0 = filho direto). Em level=core, filhos diretos são retornados
        sem os próprios filhos.
        """
        key = _children_key(element)
        result = {k: copy.deepcopy(v) for k, v in element.items() if k != key}

        if element.get("modelType") == "Property":
            await self._apply_live_value(result, submodel_id, path)

        if element.get("modelType") == "Blob" and extent == Extent.without_blob_value:
            result.pop("value", None)

        if key and element.get(key):
            if level == Level.core and depth >= 0:
                # omitido em vez de [], pois a Part 1 exige minItems 1
                return result

            result[key] = [
                await self._render(child, submodel_id, child_path, depth + 1, level, extent)
                for child, child_path in iter_children(element, path)
            ]

        return result

    async def _apply_live_value(self, result: Dict[str, Any], submodel_id: str, path: str) -> None:
        if self._registry is None:
            return

        entry = self._registry.get_value_node(submodel_id, path)
        if entry is None:
            return

        try:
            value = format_xs_value(await entry.node.get_value())
        except Exception as e:
            # sem o valor vivo, responde com o valor do modelo
            logger.warning(
                "api.serializer.live_value_failed",
                submodel_id=submodel_id,
                id_short_path=path,
                error=str(e),
            )
            return

        if value is None:
            result.pop("value", None)
        else:
            result["value"] = value

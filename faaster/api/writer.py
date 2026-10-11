"""
Escrita de valores ValueOnly — PatchSubmodelById-ValueOnly e
PatchSubmodelElementByPath-ValueOnly (IDTA-01002-3-2).

As escritas vão direto para os nós OPC UA (AAS Tipo 2): o documento AAS não
é alterado e nada é persistido em arquivo — o valor dura enquanto o servidor
estiver no ar, como uma escrita feita por um cliente OPC UA.

Hoje só Property tem valor vivo no OPC UA; coleções e o próprio submodelo
são aceitos quando os elementos endereçados no corpo são Properties.

A requisição é validada por inteiro antes da primeira escrita: um 400, 404
ou 501 nunca deixa o modelo escrito pela metade.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from faaster.interfaces.types import FaasterVariantType
from faaster.log import get_logger
from faaster.parser.creators.base import resolve_variant_type
from faaster.parser.node_registry import NodeRegistry, ValueNodeEntry

from .errors import BadRequestError, NotImplementedApiError
from .repository import join_path
from .serializer import format_xs_value


logger = get_logger(__name__)


# Faixas dos tipos inteiros do xsd (None = sem limite)
_XS_INTEGER_BOUNDS: Dict[str, Tuple[Optional[int], Optional[int]]] = {
    "xs:integer": (None, None),
    "xs:long": (-2**63, 2**63 - 1),
    "xs:int": (-2**31, 2**31 - 1),
    "xs:short": (-2**15, 2**15 - 1),
    "xs:byte": (-2**7, 2**7 - 1),
    "xs:unsignedLong": (0, 2**64 - 1),
    "xs:unsignedInt": (0, 2**32 - 1),
    "xs:unsignedShort": (0, 2**16 - 1),
    "xs:unsignedByte": (0, 2**8 - 1),
    "xs:nonNegativeInteger": (0, None),
    "xs:positiveInteger": (1, None),
    "xs:nonPositiveInteger": (None, 0),
    "xs:negativeInteger": (None, -1),
}
_XS_FLOAT_TYPES = {"xs:decimal", "xs:double", "xs:float"}

# Faixas dos tipos inteiros do nó OPC UA
_VARIANT_BOUNDS: Dict[FaasterVariantType, Tuple[int, int]] = {
    FaasterVariantType.Int16: (-2**15, 2**15 - 1),
    FaasterVariantType.Int32: (-2**31, 2**31 - 1),
    FaasterVariantType.Int64: (-2**63, 2**63 - 1),
    FaasterVariantType.UInt16: (0, 2**16 - 1),
    FaasterVariantType.UInt32: (0, 2**32 - 1),
    FaasterVariantType.UInt64: (0, 2**64 - 1),
}

_INTEGER_LEXICAL = re.compile(r"[+-]?\d+")

# Elementos sem representação ValueOnly
_NO_VALUE = {"Operation", "Capability"}


def _out_of_bounds(value: int, bounds: Tuple[Optional[int], Optional[int]]) -> bool:
    low, high = bounds
    return (low is not None and value < low) or (high is not None and value > high)


def parse_value(value: Any, value_type: Optional[str], path: str) -> Any:
    """
    Valor ValueOnly (JSON tipado, ou a forma léxica xsd como string) →
    valor Python validado contra o valueType da Property.
    """
    def invalid(reason: str = "") -> BadRequestError:
        detail = f": {reason}" if reason else ""
        return BadRequestError(
            f"Invalid value {value!r} for '{path}' ({value_type or 'xs:string'}){detail}"
        )

    if value is None:
        raise invalid("null is not a valid value")

    if value_type == "xs:boolean":
        if isinstance(value, bool):
            return value
        if value in ("true", "1"):
            return True
        if value in ("false", "0"):
            return False
        raise invalid()

    if value_type in _XS_INTEGER_BOUNDS:
        if isinstance(value, bool):
            raise invalid()
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if isinstance(value, str) and _INTEGER_LEXICAL.fullmatch(value.strip()):
            number = int(value.strip())
        elif isinstance(value, int):
            number = value
        else:
            raise invalid()
        if _out_of_bounds(number, _XS_INTEGER_BOUNDS[value_type]):
            raise invalid("out of range")
        return number

    if value_type in _XS_FLOAT_TYPES:
        if isinstance(value, bool):
            raise invalid()
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                # aceita também NaN, INF e -INF do xsd
                return float(value.strip())
            except ValueError:
                raise invalid() from None
        raise invalid()

    if not isinstance(value, str):
        raise invalid("expected a string")

    if value_type == "xs:dateTime":
        try:
            datetime.fromisoformat(value)
        except ValueError:
            raise invalid() from None

    return value


def to_node_value(value: Any, variant_type: FaasterVariantType, path: str) -> Any:
    """Valor Python validado → valor do tipo do nó OPC UA da Property."""
    if variant_type in _VARIANT_BOUNDS:
        if not isinstance(value, int) or isinstance(value, bool):
            raise BadRequestError(f"Value {value!r} for '{path}' must be an integer")
        if _out_of_bounds(value, _VARIANT_BOUNDS[variant_type]):
            raise BadRequestError(
                f"Value {value} for '{path}' is out of range for its "
                f"OPC UA node ({variant_type.value})"
            )
        return value

    if variant_type in (FaasterVariantType.Float, FaasterVariantType.Double):
        return float(value)

    if variant_type == FaasterVariantType.Boolean:
        return bool(value)

    if variant_type == FaasterVariantType.DateTime:
        return datetime.fromisoformat(value) if isinstance(value, str) else value

    if variant_type == FaasterVariantType.ByteString:
        return value.encode("utf-8") if isinstance(value, str) else value

    # String: guarda a forma léxica xsd, como no modelo
    return value if isinstance(value, str) else format_xs_value(value)


@dataclass
class ValueWrite:
    path: str
    entry: ValueNodeEntry
    value: Any
    variant_type: FaasterVariantType


class ValueWriter:
    def __init__(self, registry: Optional[NodeRegistry] = None) -> None:
        self._registry = registry

    # -------------------------------------------------------------------------
    # Planejamento (só valida, não escreve)
    # -------------------------------------------------------------------------

    def plan_submodel(self, submodel: Dict[str, Any], value: Any) -> List[ValueWrite]:
        """Corpo de PatchSubmodelById-ValueOnly: {idShort: valor, ...}."""
        return self._plan_children(
            submodel.get("submodelElements") or [], submodel["id"], "", value, "the Submodel"
        )

    def plan_element(
        self,
        element: Dict[str, Any],
        submodel_id: str,
        path: str,
        value: Any,
    ) -> List[ValueWrite]:
        model_type = element.get("modelType")

        if model_type in _NO_VALUE:
            raise BadRequestError(f"ValueOnly serialization is not applicable to {model_type}")

        if model_type == "Property":
            return [self._plan_property(element, submodel_id, path, value)]

        if model_type == "SubmodelElementCollection":
            return self._plan_children(element.get("value") or [], submodel_id, path, value, f"'{path}'")

        if model_type == "SubmodelElementList":
            children = element.get("value") or []
            if not isinstance(value, list):
                raise BadRequestError(f"The value of '{path}' must be a JSON array")
            if len(value) != len(children):
                raise BadRequestError(
                    f"The value of '{path}' must have {len(children)} items, got {len(value)}"
                )
            writes: List[ValueWrite] = []
            for index, (child, child_value) in enumerate(zip(children, value)):
                writes.extend(
                    self.plan_element(child, submodel_id, join_path(path, index=index), child_value)
                )
            return writes

        raise NotImplementedApiError(
            f"Writing the value of '{path}' ({model_type}) is not supported: "
            f"only Property values are backed by live OPC UA nodes"
        )

    def _plan_children(
        self,
        children: List[Dict[str, Any]],
        submodel_id: str,
        path: str,
        value: Any,
        owner: str,
    ) -> List[ValueWrite]:
        if not isinstance(value, dict):
            raise BadRequestError(f"The value of {owner} must be a JSON object")

        by_id_short = {child.get("idShort"): child for child in children}
        writes: List[ValueWrite] = []
        # PATCH: só os elementos presentes no corpo são alterados
        for id_short, child_value in value.items():
            child = by_id_short.get(id_short)
            if child is None:
                raise BadRequestError(f"{owner.capitalize()} has no element '{id_short}'")
            writes.extend(
                self.plan_element(child, submodel_id, join_path(path, id_short), child_value)
            )
        return writes

    def _plan_property(
        self,
        element: Dict[str, Any],
        submodel_id: str,
        path: str,
        value: Any,
    ) -> ValueWrite:
        entry = self._registry.get_value_node(submodel_id, path) if self._registry else None
        if entry is None:
            raise NotImplementedApiError(f"Property '{path}' has no live OPC UA node to write to")

        value_type = element.get("valueType")
        variant_type = resolve_variant_type(entry.value_type or value_type)
        parsed = parse_value(value, value_type, path)
        return ValueWrite(
            path=path,
            entry=entry,
            value=to_node_value(parsed, variant_type, path),
            variant_type=variant_type,
        )

    # -------------------------------------------------------------------------
    # Escrita
    # -------------------------------------------------------------------------

    async def apply(self, submodel_id: str, writes: List[ValueWrite]) -> None:
        for write in writes:
            await write.entry.node.set_value(write.value, write.variant_type)
            logger.info(
                "api.value_written",
                submodel_id=submodel_id,
                id_short_path=write.path,
                value=write.value,
            )

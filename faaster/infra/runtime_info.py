"""
Objeto ``FaasterRuntime`` no espaço de endereços (decisão D16 da proposta de dissertação).

Saúde e métricas do runtime como nós OPC UA, no namespace do Faaster, para que o agente do
Faaster Twin Manager as leia na mesma sessão da verificação de saúde, sem uma segunda porta.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from faaster.interfaces import IAddressSpace, INode
from faaster.interfaces.types import FaasterVariantType

RUNTIME_OBJECT = "FaasterRuntime"


class RuntimeInfo:
    """Handle of the published object, to reflect failures that happen after start."""

    def __init__(self, node: INode, loaded: INode, failed: INode, errors: INode) -> None:
        self.node, self._loaded, self._failed, self._errors = node, loaded, failed, errors

    async def update(self, *, loaded: List[str], failed: Dict[str, str]) -> None:
        await self._loaded.set_value(sorted(loaded), FaasterVariantType.String)
        await self._failed.set_value(_failed_list(failed), FaasterVariantType.String)
        await self._errors.set_value(len(failed), FaasterVariantType.Int32)


def _failed_list(failed: Dict[str, str]) -> List[str]:
    return [f"{name}: {reason}" for name, reason in sorted(failed.items())]


async def publish_runtime_info(
    address_space: IAddressSpace,
    *,
    version: str,
    loaded: List[str],
    failed: Dict[str, str],
) -> RuntimeInfo:
    """Cria ``Objects/FaasterRuntime`` com Version, StartedAt, ExtensionsLoaded,
    ExtensionsFailed (``"<idShort>: <categoria>"``) e ExtensionErrors.

    ``failed`` deve conter só categorias e tipos de exceção, nunca mensagens: estes nós são
    legíveis por qualquer cliente OPC UA com acesso ao servidor.
    """
    objects = await address_space.get_objects_node()
    runtime = await address_space.add_object(objects, RUNTIME_OBJECT)
    await address_space.add_variable(runtime, "Version", version, FaasterVariantType.String)
    await address_space.add_variable(
        runtime, "StartedAt", datetime.now(timezone.utc), FaasterVariantType.DateTime
    )
    loaded_node = await address_space.add_variable(
        runtime, "ExtensionsLoaded", sorted(loaded), FaasterVariantType.String, is_array=True
    )
    failed_node = await address_space.add_variable(
        runtime, "ExtensionsFailed", _failed_list(failed), FaasterVariantType.String,
        is_array=True,
    )
    errors_node = await address_space.add_variable(
        runtime, "ExtensionErrors", len(failed), FaasterVariantType.Int32
    )
    return RuntimeInfo(runtime, loaded_node, failed_node, errors_node)

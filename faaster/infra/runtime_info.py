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


async def publish_runtime_info(
    address_space: IAddressSpace,
    *,
    version: str,
    loaded: List[str],
    failed: Dict[str, str],
) -> INode:
    """Cria ``Objects/FaasterRuntime`` com Version, StartedAt, ExtensionsLoaded,
    ExtensionsFailed (``"<idShort>: <motivo>"``) e ExtensionErrors."""
    objects = await address_space.get_objects_node()
    runtime = await address_space.add_object(objects, RUNTIME_OBJECT)
    await address_space.add_variable(runtime, "Version", version, FaasterVariantType.String)
    await address_space.add_variable(
        runtime, "StartedAt", datetime.now(timezone.utc), FaasterVariantType.DateTime
    )
    await address_space.add_variable(
        runtime, "ExtensionsLoaded", sorted(loaded), FaasterVariantType.String, is_array=True
    )
    await address_space.add_variable(
        runtime,
        "ExtensionsFailed",
        [f"{name}: {reason}" for name, reason in sorted(failed.items())],
        FaasterVariantType.String,
        is_array=True,
    )
    await address_space.add_variable(
        runtime, "ExtensionErrors", len(failed), FaasterVariantType.Int32
    )
    return runtime

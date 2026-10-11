"""
AssetBinder — vínculo declarativo entre o AAS e o ativo físico.

Lê o AID (IDTA 02017) e o AIMC (IDTA 02027) do modelo carregado e liga os
pontos do ativo às Properties do AAS, sem código específico por ativo:

    norte (ativo → AAS):  Source no AID, Sink numa Property  — padrão do AIMC 2
    sul   (AAS → ativo):  Source numa Property, Sink no AID  — extensão do Faaster;
                          o AIMC 2 só prevê escrita no ativo como caso futuro

Regras:
    - AID sem AIMC: nada é vinculado (só aviso); o vínculo nunca é deduzido por nome.
    - O vínculo é dono dos nós que alimenta. Extensões, clientes OPC UA e a API
      escrevem no nó do AAS; se houver mapeamento sul, a escrita é repassada ao
      ativo. Escrita num nó só-norte é sobrescrita na próxima leitura (aviso).
    - Eco: cada nó guarda o estado esperado do ativo (último valor lido ou último
      comando enviado); uma escrita igual a ele não volta para o ativo, o que
      evita o laço norte → sul sem perder comandos rápidos (pulsos).
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Type

from faaster.binding.drivers.base import IAssetDriver, load_drivers
from faaster.binding.model import (
    AID_SEMANTIC_PREFIX,
    AIMC_SEMANTIC_PREFIX,
    AssetInterface,
    MappingConfiguration,
    MappingEndpoint,
    PropertyAffordance,
    id_short_path,
    parse_aid,
    parse_aimc,
    semantic_id,
    submodel_version,
)
from faaster.interfaces import IAddressSpace, INode
from faaster.interfaces.types import FaasterVariantType
from faaster.log import get_logger
from faaster.parser.creators.base import resolve_variant_type
from faaster.parser.node_registry import NodeRegistry


logger = get_logger(__name__)

_NO_VALUE = object()


@dataclass
class AasTarget:
    """Property do AAS que participa de um vínculo."""
    submodel_id: str
    path: str
    node: INode
    variant_type: FaasterVariantType
    last_from_asset: Any = _NO_VALUE   # último valor lido do ativo
    expected: Any = _NO_VALUE          # estado esperado: leitura ou último comando
    watch_handle: Any = None


@dataclass
class InterfaceBinding:
    interface: AssetInterface
    driver: Optional[IAssetDriver] = None
    # nome do ponto → Properties que ele alimenta (norte)
    north: Dict[str, List[AasTarget]] = field(default_factory=dict)
    # intervalos de polling (s) por ponto, quando o AIMC define
    poll: Dict[str, float] = field(default_factory=dict)


@dataclass
class SouthLink:
    target: AasTarget
    binding: InterfaceBinding
    affordance: PropertyAffordance


class AssetBinder:
    def __init__(
        self,
        address_space: IAddressSpace,
        registry: NodeRegistry,
        drivers: Optional[Dict[str, Type[IAssetDriver]]] = None,
    ) -> None:
        self._address_space = address_space
        self._registry = registry
        self._drivers = drivers
        self._bindings: Dict[Tuple[str, str], InterfaceBinding] = {}
        self._targets: Dict[Tuple[str, str], AasTarget] = {}
        self._south: Dict[Tuple[str, str], List[SouthLink]] = {}
        self._warned_overwrite: set = set()
        self._write_queue: "asyncio.Queue[Tuple[SouthLink, Any]]" = asyncio.Queue()
        self._tasks: List[asyncio.Task] = []

    # -------------------------------------------------------------------------
    # Montagem (a partir do documento; não abre conexões)
    # -------------------------------------------------------------------------

    def configure(self, document: Optional[Dict[str, Any]]) -> int:
        """
        Monta os vínculos a partir do documento AAS. Devolve o número de
        mapeamentos válidos. Pode ser chamado antes do servidor subir.
        """
        submodels = (document or {}).get("submodels") or []
        aids = [sm for sm in submodels if semantic_id(sm).startswith(AID_SEMANTIC_PREFIX)]
        aimcs = [sm for sm in submodels if semantic_id(sm).startswith(AIMC_SEMANTIC_PREFIX)]

        interfaces: Dict[Tuple[str, str], AssetInterface] = {}
        for aid in aids:
            for interface in parse_aid(aid):
                interfaces[(interface.submodel_id, interface.id_short)] = interface

        used_aids = set()
        count = 0
        for aimc in aimcs:
            version = submodel_version(semantic_id(aimc), AIMC_SEMANTIC_PREFIX)
            if version[:1] != (2,):
                logger.warning(
                    "binding.aimc.unsupported_version",
                    submodel_id=aimc.get("id"),
                    version=".".join(map(str, version)),
                    supported="2.x",
                )
                continue
            for config in parse_aimc(aimc):
                count += self._configure_mapping(aimc["id"], config, interfaces, used_aids)

        for aid in aids:
            if aid["id"] not in used_aids:
                logger.warning(
                    "binding.aid.without_aimc",
                    submodel_id=aid["id"],
                    detail="AID present but no AIMC mapping refers to it; nothing bound",
                )

        logger.info(
            "binding.configured",
            interfaces=len(self._bindings),
            north=sum(len(t) for b in self._bindings.values() for t in b.north.values()),
            south=sum(len(links) for links in self._south.values()),
        )
        return count

    def _configure_mapping(
        self,
        aimc_id: str,
        config: MappingConfiguration,
        interfaces: Dict[Tuple[str, str], AssetInterface],
        used_aids: set,
    ) -> int:
        where = {"aimc": aimc_id, "mapping_configuration": config.index}

        if config.has_transformation:
            logger.warning("binding.aimc.transformation_unsupported", **where,
                           detail="Lua transformations are not supported yet; mapping skipped")
            return 0

        sinks = {sink.id: sink for sink in config.sinks}
        if len(config.sources) != len(config.sinks) or set(sinks) != {s.id for s in config.sources}:
            logger.error("binding.aimc.unpaired", **where,
                         detail="without transformation, each SourceId needs exactly one SinkId")
            return 0

        count = 0
        for source in config.sources:
            sink = sinks[source.id]
            source_point = self._asset_point(source, interfaces)
            sink_point = self._asset_point(sink, interfaces)

            if source_point and not sink_point:
                target = self._aas_target(sink, where)
                if target is None:
                    continue
                binding = self._binding(source_point[0])
                binding.north.setdefault(source_point[1].name, []).append(target)
                interval = source.polling_interval or config.default_polling_interval
                if interval and not source_point[1].observable:
                    binding.poll[source_point[1].name] = interval
                used_aids.add(source_point[0].submodel_id)
                count += 1

            elif sink_point and not source_point:
                target = self._aas_target(source, where)
                if target is None:
                    continue
                link = SouthLink(target=target, binding=self._binding(sink_point[0]), affordance=sink_point[1])
                self._south.setdefault((target.submodel_id, target.path), []).append(link)
                used_aids.add(sink_point[0].submodel_id)
                count += 1

            elif source_point and sink_point:
                logger.error("binding.aimc.asset_to_asset", **where, source_id=source.id,
                             detail="Source and Sink both point into an AID")
            else:
                logger.warning("binding.aimc.aas_to_aas_unsupported", **where, source_id=source.id)
        return count

    def _asset_point(
        self,
        endpoint: MappingEndpoint,
        interfaces: Dict[Tuple[str, str], AssetInterface],
    ) -> Optional[Tuple[AssetInterface, PropertyAffordance]]:
        """Se a referência aponta para um ponto do AID, devolve (interface, ponto)."""
        keys = endpoint.keys
        if len(keys) < 2:
            return None
        interface = interfaces.get((keys[0][1], keys[1][1]))
        if interface is None:
            return None
        # Submodel / Interface / InteractionMetadata / properties / <ponto>
        names = [value for _, value in keys]
        if len(names) != 5 or names[2:4] != ["InteractionMetadata", "properties"]:
            logger.error("binding.aimc.unsupported_aid_reference", keys=names)
            return None
        affordance = interface.properties.get(names[4])
        if affordance is None:
            logger.error("binding.aimc.unknown_point", interface=interface.id_short, point=names[4])
            return None
        return interface, affordance

    def _aas_target(self, endpoint: MappingEndpoint, where: Dict[str, Any]) -> Optional[AasTarget]:
        if not endpoint.keys or endpoint.keys[0][0] != "Submodel":
            logger.error("binding.aimc.invalid_reference", **where, id=endpoint.id, keys=endpoint.keys)
            return None
        submodel_id = endpoint.keys[0][1]
        path = id_short_path(endpoint.keys)
        key = (submodel_id, path)
        if key in self._targets:
            return self._targets[key]
        entry = self._registry.get_value_node(submodel_id, path) if path else None
        if entry is None:
            logger.error("binding.aimc.target_not_found", **where, id=endpoint.id,
                         submodel_id=submodel_id, path=path,
                         detail="only Properties with a live OPC UA node can be bound")
            return None
        target = AasTarget(
            submodel_id=submodel_id,
            path=path,
            node=entry.node,
            variant_type=resolve_variant_type(entry.value_type),
        )
        self._targets[key] = target
        return target

    def _binding(self, interface: AssetInterface) -> InterfaceBinding:
        key = (interface.submodel_id, interface.id_short)
        if key not in self._bindings:
            self._bindings[key] = InterfaceBinding(interface=interface)
        return self._bindings[key]

    # -------------------------------------------------------------------------
    # Execução
    # -------------------------------------------------------------------------

    @property
    def is_empty(self) -> bool:
        return not self._bindings

    async def start(self) -> None:
        """Torna graváveis os nós com mapeamento sul, observa escritas e conecta os drivers."""
        drivers = self._drivers if self._drivers is not None else load_drivers()

        for key, target in self._targets.items():
            if key in self._south:
                await self._address_space.set_writable(target.node, True)
            target.watch_handle = await self._address_space.watch_value(
                target.node, self._make_watcher(target)
            )

        if self._south:
            self._tasks.append(asyncio.create_task(self._write_worker(), name="binding:south"))

        for binding in self._bindings.values():
            interface = binding.interface
            driver_cls = drivers.get(interface.scheme)
            if driver_cls is None:
                logger.error("binding.driver.not_found", base=interface.base, scheme=interface.scheme)
                continue
            binding.driver = driver_cls(interface)
            observe = [interface.properties[name] for name in binding.north]
            try:
                await binding.driver.start(observe, self._make_receiver(binding), binding.poll)
            except NotImplementedError as exc:
                logger.error("binding.driver.unsupported", base=interface.base, error=str(exc))
                binding.driver = None

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for target in self._targets.values():
            if target.watch_handle is not None:
                self._address_space.unwatch_value(target.watch_handle)
                target.watch_handle = None
        for binding in self._bindings.values():
            if binding.driver is not None:
                await binding.driver.stop()

    # norte -------------------------------------------------------------------

    def _make_receiver(self, binding: InterfaceBinding):
        async def on_value(affordance: PropertyAffordance, value: Any) -> None:
            for target in binding.north.get(affordance.name, []):
                converted = _to_aas(value, target.variant_type)
                if converted is None:
                    continue
                target.last_from_asset = target.expected = converted
                await self._address_space.set_value(target.node, converted, target.variant_type)
        return on_value

    # sul ---------------------------------------------------------------------

    def _make_watcher(self, target: AasTarget):
        key = (target.submodel_id, target.path)

        async def on_write(value: Any) -> None:
            if value is None or value == target.expected:
                return  # eco da leitura do ativo, ou comando já enviado
            links = self._south.get(key)
            if links:
                target.expected = value
                for link in links:
                    self._write_queue.put_nowait((link, value))
            elif key not in self._warned_overwrite:
                self._warned_overwrite.add(key)
                logger.warning(
                    "binding.write_to_asset_owned_node",
                    submodel_id=target.submodel_id,
                    path=target.path,
                    detail="node is fed by the asset and has no AAS→asset mapping; "
                           "the value will be overwritten by the next reading",
                )
        return on_write

    async def _write_worker(self) -> None:
        while True:
            link, value = await self._write_queue.get()
            driver = link.binding.driver
            try:
                if driver is None:
                    raise ConnectionError("no driver for this interface")
                await driver.write(link.affordance, value)
                logger.info(
                    "binding.written_to_asset",
                    base=link.binding.interface.base,
                    point=link.affordance.name,
                    path=link.target.path,
                    value=value,
                )
            except Exception as exc:
                logger.error(
                    "binding.write_to_asset_failed",
                    base=link.binding.interface.base,
                    point=link.affordance.name,
                    path=link.target.path,
                    value=value,
                    error=str(exc) or type(exc).__name__,
                )
                await self._restore(link.target)

    async def _restore(self, target: AasTarget) -> None:
        """Escrita no ativo falhou: devolve ao nó o último valor lido do ativo."""
        if target.last_from_asset is not _NO_VALUE:
            target.expected = target.last_from_asset
            await self._address_space.set_value(target.node, target.last_from_asset, target.variant_type)


_INTEGER_VARIANTS = {
    FaasterVariantType.Int16, FaasterVariantType.Int32, FaasterVariantType.Int64,
    FaasterVariantType.UInt16, FaasterVariantType.UInt32, FaasterVariantType.UInt64,
}


def _to_aas(value: Any, variant_type: FaasterVariantType) -> Any:
    """Valor lido do ativo → tipo do nó da Property."""
    if value is None:
        return None
    if variant_type == FaasterVariantType.Boolean:
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1")
        return bool(value)
    if variant_type in _INTEGER_VARIANTS:
        return int(value)
    if variant_type in (FaasterVariantType.Float, FaasterVariantType.Double):
        return float(value)
    if variant_type == FaasterVariantType.String:
        return value if isinstance(value, str) else str(value)
    return value

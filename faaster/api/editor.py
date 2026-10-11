"""
Escrita estrutural de submodelos e elementos (IDTA-01002-3-2): PostSubmodel,
PutSubmodelById, PatchSubmodelById (normal e $metadata), DeleteSubmodelById,
PostSubmodelElement(ByPath), PutSubmodelElementByPath,
PatchSubmodelElementByPath (normal e $metadata) e DeleteSubmodelElementByPath.

Cada alteração vale para o modelo servido pela API E para o address space
OPC UA (AAS Tipo 2), e nada é gravado no arquivo do modelo. O modelo antigo e
o novo são reconciliados elemento a elemento, mexendo só no que mudou:

  - Elemento novo ou removido: a subárvore OPC UA é criada (como na partida,
    mas sem historizar) ou removida.
  - Atualização no lugar: num Submodel, SubmodelElementCollection ou Property
    que continua com os mesmos atributos de runtime, só os nós de metadados
    são recriados e os valores gravados nos nós existentes. NodeIds,
    assinaturas OPC UA, HDA e extensões continuam funcionando.
  - Reconstrução: qualquer outra mudança remove e recria a subárvore.
  - 409: remover ou reconstruir uma subárvore com nós em uso pelo runtime
    (Properties historizadas ou Operations vinculadas a uma extensão) é
    recusado; os valores continuam graváveis com PATCH .../$value.

Tudo é validado (metamodelo, conflitos, valores) antes da primeira alteração.
"""
import asyncio
import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from faaster.aas_metamodel.models.submodel import Submodel
from faaster.aas_metamodel.submodel_element_processor import SubmodelElementProcessor
from faaster.log import get_logger
from faaster.parser import AASParser, NodeRegistry
from faaster.parser.creators.base import resolve_variant_type

from .errors import BadRequestError, ConflictError, NotFoundError
from .modifiers import _METADATA_EXCLUDE
from .repository import (
    CHILDREN_BY_ID_SHORT,
    CHILDREN_BY_INDEX,
    AASRepository,
    iter_children,
    join_path,
    parse_id_short_path,
)
from .serializer import format_xs_value
from .writer import ValueWrite, ValueWriter, parse_value, to_node_value


logger = get_logger(__name__)


# Atributos de uma Property que o runtime usa (tipo do nó, HDA, índice por
# semanticId das extensões): mudar qualquer um exige recriar o nó
_PROPERTY_RUNTIME_KEYS = ("valueType", "category", "extensions", "semanticId")


def _children_key(element: Dict[str, Any]) -> Optional[str]:
    model_type = element.get("modelType")
    return CHILDREN_BY_ID_SHORT.get(model_type) or CHILDREN_BY_INDEX.get(model_type)


def _parent_path(path: str) -> str:
    """Pai de "A.B[2]" é "A.B"; de "A.B" é "A"; de "A" é ""."""
    if path.endswith("]"):
        return path[: path.rindex("[")]
    return path.rsplit(".", 1)[0] if "." in path else ""


def _own(element: Dict[str, Any]) -> Dict[str, Any]:
    """Atributos do próprio elemento — sem os filhos nem o valor de uma Property."""
    skip = {"submodelElements", _children_key(element)}
    if element.get("modelType") == "Property":
        skip.add("value")
    return {k: v for k, v in element.items() if k not in skip}


def _require_value_types(elements: List[Dict[str, Any]], path: str = "") -> None:
    """valueType é obrigatório em Property e Range (o metamodelo assume xs:int)."""
    for element in elements:
        element_path = join_path(path, element.get("idShort")) if element.get("idShort") else path
        if element.get("modelType") in ("Property", "Range") and not element.get("valueType"):
            raise BadRequestError(f"{element['modelType']} '{element_path}' requires a valueType")
        _require_value_types([child for child, _ in iter_children(element, element_path)], element_path)


def _validate_submodel(submodel: Dict[str, Any]) -> Submodel:
    if not isinstance(submodel, dict):
        raise BadRequestError("The request body must be a Submodel JSON object")
    _require_value_types(submodel.get("submodelElements") or [])
    try:
        # cópia: alguns modelos do aas_metamodel alteram os dicts recebidos
        return Submodel(**copy.deepcopy(submodel))
    except Exception as e:
        raise BadRequestError(f"Invalid Submodel: {e}") from None


def _validate_element(element: Dict[str, Any]) -> Any:
    if not isinstance(element, dict) or not element.get("modelType"):
        raise BadRequestError("The request body must be a SubmodelElement JSON object with a modelType")
    _require_value_types([element])
    module, model_type = SubmodelElementProcessor.process_elements(element)
    cls = getattr(module, model_type, None)
    if cls is None:
        raise BadRequestError(f"Unknown SubmodelElement modelType '{model_type}'")
    try:
        return cls(**copy.deepcopy(element))
    except Exception as e:
        raise BadRequestError(f"Invalid {model_type}: {e}") from None


def _container_children(container: Dict[str, Any], create: bool = False) -> Tuple[List[Dict[str, Any]], bool]:
    """(lista de filhos, filhos endereçados por índice?) do submodelo ou elemento."""
    if container.get("modelType") == "Submodel":
        key, by_index = "submodelElements", False
    else:
        key = _children_key(container)
        if key is None:
            raise BadRequestError(
                f"{container.get('modelType')} '{container.get('idShort')}' cannot contain SubmodelElements"
            )
        by_index = container.get("modelType") in CHILDREN_BY_INDEX
    if key not in container:
        if not create:
            return [], by_index
        container[key] = []
    return container[key], by_index


def _locate(submodel: Dict[str, Any], path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], int]:
    """(pai, lista que contém o elemento, índice nela) dentro de uma cópia do submodelo."""
    tokens = parse_id_short_path(path)
    not_found = NotFoundError(f"SubmodelElement with idShortPath '{path}' not found in Submodel '{submodel['id']}'")

    parent: Dict[str, Any] = submodel
    for position, token in enumerate(tokens):
        children, by_index = _container_children(parent)
        if isinstance(token, int):
            if not by_index or token >= len(children):
                raise not_found
            index = token
        else:
            if by_index:
                raise not_found
            index = next((i for i, c in enumerate(children) if c.get("idShort") == token), None)
            if index is None:
                raise not_found
        if position == len(tokens) - 1:
            return parent, children, index
        parent = children[index]
        if _children_key(parent) is None:
            raise not_found
    raise not_found


def _drop_if_empty(container: Dict[str, Any], children: List[Dict[str, Any]]) -> None:
    # a Part 1 exige listas de filhos não vazias: some com a chave
    if not children:
        for key, value in list(container.items()):
            if value is children:
                del container[key]


@dataclass
class _Plan:
    """Alterações no address space OPC UA, decididas antes de executar."""
    removes: List[str] = field(default_factory=list)
    creates: List[Tuple[str, Any]] = field(default_factory=list)       # (pai, modelo)
    refreshes: List[Tuple[str, Any]] = field(default_factory=list)     # (idShortPath, modelo)
    writes: List[ValueWrite] = field(default_factory=list)
    restores: List[Tuple[str, Any]] = field(default_factory=list)      # (idShortPath, valor vivo)
    new_submodel: Optional[Submodel] = None
    in_use: List[str] = field(default_factory=list)


class StructureEditor:
    def __init__(
        self,
        repository: AASRepository,
        registry: Optional[NodeRegistry] = None,
        sync: Optional[AASParser] = None,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._sync = sync
        self._writer = ValueWriter(registry)
        # alterações estruturais em série: cada uma lê o modelo e o address space
        self._lock = asyncio.Lock()

    # =========================================================================
    # Submodelos
    # =========================================================================

    async def create_submodel(self, body: Dict[str, Any]) -> Dict[str, Any]:
        async with self._lock:
            model = _validate_submodel(body)
            if self._repository.has_submodel(model.id):
                raise ConflictError(f"Submodel with id '{model.id}' already exists")

            submodel = copy.deepcopy(body)
            if self._sync is not None:
                await self._sync.add_submodel(model)
            self._repository.put_submodel(submodel)
            logger.info("api.submodel.created", submodel_id=model.id)
            return submodel

    async def put_submodel(self, submodel_id: str, body: Dict[str, Any]) -> bool:
        """Substitui o submodelo ou o cria; retorna True se criou."""
        if isinstance(body, dict) and body.get("id") != submodel_id:
            raise BadRequestError("The id of the Submodel in the body must match the submodelIdentifier")
        if not self._repository.has_submodel(submodel_id):
            await self.create_submodel(body)
            return True

        async with self._lock:
            await self._replace_submodel(copy.deepcopy(body), preserve_live=False)
        return False

    async def patch_submodel(self, submodel_id: str, body: Dict[str, Any]) -> None:
        """PATCH com level=core ou $metadata: em ambos os filhos ficam inalterados."""
        async with self._lock:
            old = self._repository.get_submodel(submodel_id)
            if not isinstance(body, dict):
                raise BadRequestError("The request body must be a Submodel JSON object")
            if body.get("id", submodel_id) != submodel_id:
                raise BadRequestError("The id of the Submodel cannot be changed")

            new = {k: copy.deepcopy(v) for k, v in body.items() if k != "submodelElements"}
            new["id"] = submodel_id
            if "submodelElements" in old:
                new["submodelElements"] = copy.deepcopy(old["submodelElements"])
            # os filhos vêm do modelo guardado: seus valores não podem
            # sobrescrever os valores vivos dos nós
            await self._replace_submodel(new, preserve_live=True)

    async def _replace_submodel(self, new: Dict[str, Any], preserve_live: bool) -> None:
        submodel_id = new.get("id")
        old = self._repository.get_submodel(submodel_id)
        model = _validate_submodel(new)

        plan = _Plan()
        if self._sync is not None:
            if old.get("idShort") != new.get("idShort"):
                # o idShort do submodelo é a raiz dos paths do runtime (extensões, HDA)
                self._plan_remove(plan, submodel_id, "")
                plan.new_submodel = model
            else:
                if _own(old) != _own(new):
                    plan.refreshes.append(("", model))
                await self._plan_children(
                    plan, submodel_id, "",
                    old.get("submodelElements") or [], new.get("submodelElements") or [],
                    preserve_live,
                )
        await self._execute(plan, submodel_id, new.get("idShort"), "replace")

        self._repository.put_submodel(new)
        logger.info("api.submodel.replaced", submodel_id=submodel_id)

    async def delete_submodel(self, submodel_id: str, aas_id: Optional[str] = None) -> None:
        async with self._lock:
            submodel = self._repository.get_submodel(submodel_id)
            plan = _Plan()
            self._plan_remove(plan, submodel_id, "")
            await self._execute(plan, submodel_id, submodel.get("idShort"), "delete")
            self._repository.delete_submodel(submodel_id)
            if aas_id is not None:
                self._repository.remove_submodel_reference(aas_id, submodel_id)
            logger.info("api.submodel.deleted", submodel_id=submodel_id)

    # =========================================================================
    # Elementos
    # =========================================================================

    async def create_element(
        self,
        submodel_id: str,
        parent_path: str,
        body: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """Cria sob o submodelo (parent_path "") ou um elemento; retorna (idShortPath, elemento)."""
        async with self._lock:
            submodel = copy.deepcopy(self._repository.get_submodel(submodel_id))
            element_model = _validate_element(body)

            if parent_path:
                parent_container, siblings, index = _locate(submodel, parent_path)
                parent = siblings[index]
            else:
                parent = submodel
            children, by_index = _container_children(parent, create=True)

            if by_index:
                # em SubmodelElementList o elemento vai para o fim da lista
                path = join_path(parent_path, index=len(children))
            else:
                id_short = body.get("idShort")
                if not id_short:
                    raise BadRequestError("The idShort of the new SubmodelElement is required")
                if any(c.get("idShort") == id_short for c in children):
                    raise ConflictError(f"SubmodelElement '{join_path(parent_path, id_short)}' already exists")
                path = join_path(parent_path, id_short)

            element = copy.deepcopy(body)
            children.append(element)
            _validate_submodel(submodel)

            if self._sync is not None:
                await self._sync.add_submodel_element(
                    submodel_id, submodel.get("idShort"), parent_path, element_model
                )
            self._repository.put_submodel(submodel)
            logger.info("api.element.created", submodel_id=submodel_id, id_short_path=path)
            return path, element

    async def put_element(self, submodel_id: str, path: str, body: Dict[str, Any]) -> bool:
        """Substitui o elemento ou o cria (o pai precisa existir); retorna True se criou."""
        last = parse_id_short_path(path)[-1]
        if isinstance(last, str) and isinstance(body, dict) and body.get("idShort") != last:
            raise BadRequestError(f"The idShort of the SubmodelElement in the body must be '{last}'")

        try:
            self._repository.get_submodel_element(submodel_id, path)
        except NotFoundError:
            if isinstance(last, int):
                raise
            await self.create_element(submodel_id, _parent_path(path), body)
            return True

        async with self._lock:
            await self._replace_element(submodel_id, path, copy.deepcopy(body), preserve_live=False)
        return False

    async def patch_element(
        self,
        submodel_id: str,
        path: str,
        body: Dict[str, Any],
        metadata_only: bool,
    ) -> None:
        """PATCH com level=core (filhos inalterados) ou $metadata (valores inalterados)."""
        async with self._lock:
            old = self._repository.get_submodel_element(submodel_id, path)
            if not isinstance(body, dict):
                raise BadRequestError("The request body must be a SubmodelElement JSON object")
            model_type = old.get("modelType")
            if body.get("modelType", model_type) != model_type:
                raise BadRequestError(f"The modelType of '{path}' ({model_type}) cannot be changed")
            if body.get("idShort", old.get("idShort")) != old.get("idShort"):
                raise BadRequestError(f"The idShort of '{path}' cannot be changed")

            keep = _METADATA_EXCLUDE.get(model_type, set()) if metadata_only else {_children_key(old)}
            new = {k: copy.deepcopy(v) for k, v in body.items() if k not in keep}
            new["modelType"] = model_type
            if "idShort" in old:
                new["idShort"] = old["idShort"]
            for key in keep:
                if key in old:
                    new[key] = copy.deepcopy(old[key])

            # em level=core os filhos vêm do modelo guardado: só a própria
            # Property (PATCH normal) traz um valor novo para o nó
            preserve_live = metadata_only or _children_key(old) is not None
            await self._replace_element(submodel_id, path, new, preserve_live=preserve_live)

    async def _replace_element(
        self,
        submodel_id: str,
        path: str,
        new: Dict[str, Any],
        preserve_live: bool,
    ) -> None:
        submodel = copy.deepcopy(self._repository.get_submodel(submodel_id))
        _, siblings, index = _locate(submodel, path)
        old = siblings[index]
        siblings[index] = new
        _validate_element(new)
        _validate_submodel(submodel)

        plan = _Plan()
        if self._sync is not None:
            await self._plan_element(plan, submodel_id, path, old, new, preserve_live)
        await self._execute(plan, submodel_id, submodel.get("idShort"), "replace")

        self._repository.put_submodel(submodel)
        logger.info("api.element.replaced", submodel_id=submodel_id, id_short_path=path)

    async def delete_element(self, submodel_id: str, path: str) -> None:
        async with self._lock:
            submodel = copy.deepcopy(self._repository.get_submodel(submodel_id))
            parent, siblings, index = _locate(submodel, path)
            del siblings[index]
            _drop_if_empty(parent, siblings)

            plan = _Plan()
            self._plan_remove(plan, submodel_id, path)
            await self._execute(plan, submodel_id, submodel.get("idShort"), "delete")
            self._repository.put_submodel(submodel)
            logger.info("api.element.deleted", submodel_id=submodel_id, id_short_path=path)

    # =========================================================================
    # Reconciliação com o address space OPC UA
    # =========================================================================

    def _plan_remove(self, plan: _Plan, submodel_id: str, path: str) -> None:
        if self._registry is not None:
            plan.in_use.extend(self._registry.nodes_in_use(submodel_id, path))
        plan.removes.append(path)

    async def _plan_children(
        self,
        plan: _Plan,
        submodel_id: str,
        parent_path: str,
        old_children: List[Dict[str, Any]],
        new_children: List[Dict[str, Any]],
        preserve_live: bool,
    ) -> None:
        old_by_id = {c.get("idShort"): c for c in old_children}
        new_by_id = {c.get("idShort"): c for c in new_children}
        if len(new_by_id) != len(new_children):
            raise BadRequestError(f"Duplicate idShort among the children of '{parent_path or submodel_id}'")

        for id_short in old_by_id.keys() - new_by_id.keys():
            self._plan_remove(plan, submodel_id, join_path(parent_path, id_short))

        for id_short, child in new_by_id.items():
            child_path = join_path(parent_path, id_short)
            if id_short in old_by_id:
                await self._plan_element(plan, submodel_id, child_path, old_by_id[id_short], child, preserve_live)
            else:
                plan.creates.append((parent_path, _validate_element(child)))

    async def _plan_element(
        self,
        plan: _Plan,
        submodel_id: str,
        path: str,
        old: Dict[str, Any],
        new: Dict[str, Any],
        preserve_live: bool,
    ) -> None:
        if old == new:
            return

        model_type = old.get("modelType")
        has_node = self._registry is not None and self._registry.get_element_node(submodel_id, path) is not None
        same_type = has_node and model_type == new.get("modelType")

        if same_type and model_type == "SubmodelElementCollection":
            if _own(old) != _own(new):
                plan.refreshes.append((path, _validate_element(new)))
            await self._plan_children(
                plan, submodel_id, path, old.get("value") or [], new.get("value") or [], preserve_live
            )
            return

        if same_type and model_type == "Property" and all(
            old.get(k) == new.get(k) for k in _PROPERTY_RUNTIME_KEYS
        ):
            if _own(old) != _own(new):
                plan.refreshes.append((path, _validate_element(new)))
            if not preserve_live:
                await self._plan_value_write(plan, submodel_id, path, new)
            return

        # reconstrução: remove a subárvore e cria de novo a partir do modelo
        self._plan_remove(plan, submodel_id, path)
        plan.creates.append((_parent_path(path), _validate_element(new)))
        if preserve_live:
            live = await self._live_value(submodel_id, path, old, new)
            if live is not None:
                plan.restores.append((path, live))

    async def _plan_value_write(self, plan: _Plan, submodel_id: str, path: str, prop: Dict[str, Any]) -> None:
        """Grava o valor do corpo no nó, se diferente do valor vivo (validado já aqui)."""
        entry = self._registry.get_value_node(submodel_id, path)
        if entry is None or prop.get("value") is None:
            return
        variant_type = resolve_variant_type(entry.value_type)
        value = to_node_value(parse_value(prop["value"], prop.get("valueType"), path), variant_type, path)
        if format_xs_value(await entry.node.get_value()) != format_xs_value(value):
            plan.writes.append(ValueWrite(path=path, entry=entry, value=value, variant_type=variant_type))

    async def _execute(self, plan: _Plan, submodel_id: str, submodel_id_short: str, action: str) -> None:
        if plan.in_use:
            raise ConflictError(
                f"Cannot {action} it: elements in use by the runtime would be removed "
                f"({', '.join(sorted(set(plan.in_use)))}). Values can still be written with PATCH .../$value"
            )
        if self._sync is None:
            return

        for path in plan.removes:
            await self._sync.remove(submodel_id, path)
        if plan.new_submodel is not None:
            await self._sync.add_submodel(plan.new_submodel)
        for parent_path, element in plan.creates:
            await self._sync.add_submodel_element(submodel_id, submodel_id_short, parent_path, element)
        for path, model in plan.refreshes:
            await self._sync.refresh_metadata(submodel_id, path, model)
        await self._writer.apply(submodel_id, plan.writes)
        for path, value in plan.restores:
            await self._restore_live_value(submodel_id, path, value)

    async def _live_value(
        self,
        submodel_id: str,
        path: str,
        old: Dict[str, Any],
        new: Dict[str, Any],
    ) -> Optional[Any]:
        """Valor vivo a preservar ao recriar uma Property em PATCH $metadata."""
        if self._registry is None or new.get("modelType") != "Property":
            return None
        if old.get("valueType") != new.get("valueType"):
            return None
        entry = self._registry.get_value_node(submodel_id, path)
        return await entry.node.get_value() if entry is not None else None

    async def _restore_live_value(self, submodel_id: str, path: str, value: Any) -> None:
        entry = self._registry.get_value_node(submodel_id, path) if self._registry else None
        if entry is None:
            return
        try:
            await entry.node.set_value(value, resolve_variant_type(entry.value_type))
        except Exception as e:
            logger.warning("api.element.live_value_lost", id_short_path=path, error=str(e))

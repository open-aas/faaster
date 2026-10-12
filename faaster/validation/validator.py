"""
Validação do modelo AAS e das extensões antes da implantação (decisão D15).

Etapas (numeração do pipeline da proposta de dissertação, §5.6):
    4  metamodel   — o modelo carrega e passa nas constraints AASd (bloqueante)
    6  operations  — cada Operation tem método snake_case na extensão (aviso)
    7  extensions  — submodelo com variáveis dinâmicas ou Operations tem extensão; cada
                     ``get_node("…")`` literal aponta para uma variável dinâmica (bloqueante)
    8  dynamic     — Qualifier faaster:dynamic booleano; políticas faaster:hda:* válidas e só
                     em variáveis dinâmicas; nomes de Extension únicos, AASd-077 (bloqueante)

As extensões são código do pacote do usuário: são lidas por AST e nunca importadas.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Set

from faaster.extensions.loader import _to_pascal_case, _to_snake_case
from faaster.hda.policies import LEVEL_REFRESH, extract_policy, has_hda_policy
from faaster.loader.factory import LoaderFactory
from faaster.parser.dynamic import DYNAMIC_QUALIFIER, LEGACY_CATEGORY

from .report import Report, Stage

_BOOLEAN = {"true", "false", "1", "0"}


@dataclass
class _Submodel:
    id_short: str
    dynamic_paths: Set[str] = field(default_factory=set)  # relativos ao submodelo
    operations: List[str] = field(default_factory=list)


@dataclass
class _Extension:
    file: str
    methods: Optional[Set[str]] = None  # None: classe não encontrada
    get_nodes: List[tuple] = field(default_factory=list)  # (linha, path)
    error: Optional[str] = None


async def validate(model_path: Path | str, sources_dir: Path | str = "sources") -> Report:
    model_path, sources_dir = Path(model_path), Path(sources_dir)
    metamodel = Stage(4, "metamodel", blocking=True)
    operations = Stage(6, "operations", blocking=False)
    extensions = Stage(7, "extensions", blocking=True)
    dynamic = Stage(8, "dynamic", blocking=True)
    report = Report([metamodel, operations, extensions, dynamic])

    try:
        environment = await LoaderFactory.create(str(model_path)).load(model_path)
    except Exception as exc:  # noqa: BLE001 - qualquer falha de carga reprova a etapa 4
        metamodel.error(f"{type(exc).__name__}: {exc}")
        for stage in (operations, extensions, dynamic):
            stage.skipped = True
        return report

    for submodel in environment.submodels or []:
        info = _Submodel(submodel.id_short or "")
        for element in submodel.submodel_elements or []:
            data = element.model_dump(by_alias=True, exclude_none=True, mode="json")
            _walk(data, [], info, dynamic)
        _check_extension(info, sources_dir, operations, extensions)
    return report


# ------------------------------------------------------------------ modelo


def _walk(element: Dict[str, Any], parents: List[str], sm: _Submodel, stage: Stage) -> None:
    id_short = element.get("idShort") or ""
    path = "/".join([*parents, id_short])
    where = f"{sm.id_short}/{path}"
    model_type = element.get("modelType")

    _check_extension_names(element, where, stage)
    if model_type == "Operation":
        sm.operations.append(id_short)
    if model_type == "Property":
        is_dynamic = _check_dynamic(element, where, stage)
        if is_dynamic:
            sm.dynamic_paths.add(f"{path}/Value")
        _check_hda(element, where, is_dynamic, sm, path, stage)

    if model_type in ("SubmodelElementCollection", "SubmodelElementList"):
        for child in element.get("value") or []:
            if isinstance(child, dict):
                _walk(child, [*parents, id_short], sm, stage)


def _check_dynamic(element: Dict[str, Any], where: str, stage: Stage) -> bool:
    for qualifier in element.get("qualifiers") or []:
        if qualifier.get("type") == DYNAMIC_QUALIFIER:
            value = str(qualifier.get("value", "")).strip().lower()
            if value not in _BOOLEAN:
                stage.error(
                    f"{where}: Qualifier {DYNAMIC_QUALIFIER} must be a boolean, got {value!r}",
                    where,
                )
                return False
            return value in ("true", "1")
    if element.get("category") == LEGACY_CATEGORY:
        stage.warning(
            f"{where}: category VARIABLE is deprecated (AAS v3.1); "
            f"use the Qualifier {DYNAMIC_QUALIFIER}",
            where,
        )
        return True
    return False


def _check_hda(element, where, is_dynamic, sm: _Submodel, path: str, stage: Stage) -> None:
    exts = [SimpleNamespace(name=e.get("name"), value=e.get("value"))
            for e in element.get("extensions") or []]  # fmt: skip
    if not has_hda_policy(exts):
        return
    if not is_dynamic:
        stage.error(f"{where}: faaster:hda:* policy on a property that is not dynamic", where)
        return
    try:
        policy = extract_policy(exts)
    except ValueError as exc:
        stage.error(f"{where}: {exc}", where)
        return
    for level in getattr(policy, "levels", None) or LEVEL_REFRESH:
        sm.dynamic_paths.add(f"{path}/Value@{level}")


def _check_extension_names(element: Dict[str, Any], where: str, stage: Stage) -> None:
    names = [e.get("name") for e in element.get("extensions") or []]
    duplicated = sorted({n for n in names if n and names.count(n) > 1})
    if duplicated:
        stage.error(f"{where}: duplicated Extension names {duplicated} (AASd-077)", where)


# ------------------------------------------------------------------ extensões (AST)


def _check_extension(sm: _Submodel, sources: Path, ops: Stage, exts: Stage) -> None:
    snake = _to_snake_case(sm.id_short)
    needs_extension = bool(sm.dynamic_paths or sm.operations)
    files = _extension_files(sources, snake)
    if not files:
        if needs_extension:
            exts.error(
                f"submodel {sm.id_short} has dynamic variables or Operations but no extension "
                f"({sources}/{snake}.py or {sources}/{snake}/__init__.py)",
                sm.id_short,
            )
        return

    extension = _analyze(files, _to_pascal_case(snake))
    if extension.error:
        exts.error(f"{extension.file}: {extension.error}", sm.id_short)
        return
    if extension.methods is None:
        exts.error(f"{extension.file}: class {_to_pascal_case(snake)} not found", sm.id_short)
        return
    for line, path in extension.get_nodes:
        if path not in sm.dynamic_paths:
            exts.error(
                f"{extension.file} line {line}: get_node({path!r}) does not match a dynamic "
                f"variable of submodel {sm.id_short}",
                f"{sm.id_short}/{path}",
            )
    for op in sm.operations:
        method = _to_snake_case(op)
        if method not in extension.methods:
            ops.error(
                f"Operation {sm.id_short}/{op} has no method {method}() in class "
                f"{_to_pascal_case(snake)}; it will return []",
                f"{sm.id_short}/{op}",
            )


def _extension_files(sources: Path, snake: str) -> List[Path]:
    package = sources / snake
    if (package / "__init__.py").is_file():
        return sorted(package.rglob("*.py"))
    script = sources / f"{snake}.py"
    return [script] if script.is_file() else []


def _analyze(files: List[Path], class_name: str) -> _Extension:
    result = _Extension(file=str(files[0]))
    for file in files:
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        except SyntaxError as exc:
            result.file, result.error = str(file), f"syntax error: {exc.msg} (line {exc.lineno})"
            return result
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                result.file = str(file)
                result.methods = {
                    n.name for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                }  # fmt: skip
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get_node"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                result.get_nodes.append((node.lineno, node.args[0].value))
    return result

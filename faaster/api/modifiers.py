"""
Modificadores de conteúdo (Content) da API HTTP/REST: $value, $metadata,
$reference e $path — IDTA-01002-3-2 §SerializationModifiers, com o formato
de cada um definido na Part 1 (IDTA-01001-3-2 §Mappings).

São funções puras sobre a serialização normal, que já chega aqui com os
valores vivos do OPC UA e com level/extent aplicados pelo AASSerializer.
"""
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .errors import BadRequestError
from .repository import iter_children


# -----------------------------------------------------------------------------
# ValueOnly ($value)
# -----------------------------------------------------------------------------

_INTEGER_TYPES = {
    "xs:integer", "xs:long", "xs:int", "xs:short", "xs:byte",
    "xs:nonNegativeInteger", "xs:positiveInteger", "xs:unsignedLong",
    "xs:unsignedInt", "xs:unsignedShort", "xs:unsignedByte",
    "xs:nonPositiveInteger", "xs:negativeInteger",
}
_FLOAT_TYPES = {"xs:decimal", "xs:double", "xs:float"}

# Sem representação ValueOnly (Part 2, tabela de aplicabilidade)
_NO_VALUE_ONLY = {"Operation", "Capability"}


def typed_value(value: Optional[str], value_type: Optional[str]) -> Any:
    """
    Forma léxica xsd → valor JSON: xs:boolean vira boolean, tipos numéricos
    viram number e o resto permanece string. Valores que não convertem
    (ex.: "NaN", "INF") ficam como string, sem perda.
    """
    if value is None:
        return None

    if value_type == "xs:boolean":
        if value in ("true", "1"):
            return True
        if value in ("false", "0"):
            return False
        return value

    try:
        if value_type in _INTEGER_TYPES:
            return int(value)
        if value_type in _FLOAT_TYPES:
            number = float(value)
            # json não representa NaN/INF — mantém a forma léxica
            if number != number or number in (float("inf"), float("-inf")):
                return value
            return number
    except ValueError:
        return value

    return value


def _value_only_children(element: Dict[str, Any], key: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for child in element.get(key) or []:
        if child.get("modelType") in _NO_VALUE_ONLY:
            continue
        value = value_only(child)
        if value is not None:
            result[child.get("idShort")] = value
    return result


def value_only(element: Dict[str, Any]) -> Any:
    """ValueOnly de um SubmodelElement (sem o idShort na raiz)."""
    model_type = element.get("modelType")

    if model_type == "Property":
        return typed_value(element.get("value"), element.get("valueType"))

    if model_type == "MultiLanguageProperty":
        if "value" not in element:
            return None
        return [{ls["language"]: ls["text"]} for ls in element["value"]]

    if model_type == "Range":
        result = {}
        for bound in ("min", "max"):
            if bound in element:
                result[bound] = typed_value(element[bound], element.get("valueType"))
        return result or None

    if model_type in ("File", "Blob"):
        result = {"contentType": element.get("contentType")}
        if "value" in element:
            result["value"] = element["value"]
        return result

    if model_type == "ReferenceElement":
        return element.get("value")

    if model_type in ("RelationshipElement", "AnnotatedRelationshipElement"):
        result = {k: element[k] for k in ("first", "second") if k in element}
        if model_type == "AnnotatedRelationshipElement" and element.get("annotations"):
            result["annotations"] = _value_only_children(element, "annotations")
        return result

    if model_type == "Entity":
        result = {"statements": _value_only_children(element, "statements")}
        for key in ("entityType", "globalAssetId"):
            if key in element:
                result[key] = element[key]
        if element.get("specificAssetIds"):
            result["specificAssetIds"] = [
                {sa["name"]: sa["value"]} for sa in element["specificAssetIds"]
            ]
        return result

    if model_type == "BasicEventElement":
        return {"observed": element.get("observed")}

    if model_type == "SubmodelElementCollection":
        # em level=core, coleções-filhas chegam sem "value" e viram {}
        return _value_only_children(element, "value")

    if model_type == "SubmodelElementList":
        return [
            value_only(child)
            for child in element.get("value") or []
            if child.get("modelType") not in _NO_VALUE_ONLY
        ]

    return None


def element_value_only(element: Dict[str, Any]) -> Any:
    """$value de um elemento requisitado diretamente pelo idShortPath."""
    if element.get("modelType") in _NO_VALUE_ONLY:
        raise BadRequestError(
            f"ValueOnly serialization is not applicable to {element.get('modelType')}"
        )
    return value_only(element)


def submodel_value_only(submodel: Dict[str, Any]) -> Dict[str, Any]:
    return _value_only_children(submodel, "submodelElements")


def elements_value_only(elements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Página de GetAllSubmodelElements-ValueOnly: um objeto idShort → valor."""
    return _value_only_children({"elements": elements}, "elements")


# -----------------------------------------------------------------------------
# Metadata ($metadata)
# -----------------------------------------------------------------------------

# Atributos de valor (e filhos) removidos na serialização Metadata
_METADATA_EXCLUDE = {
    "Submodel": {"submodelElements"},
    "Property": {"value", "valueId"},
    "MultiLanguageProperty": {"value", "valueId"},
    "Range": {"min", "max"},
    "File": {"value", "contentType"},
    "Blob": {"value", "contentType"},
    "ReferenceElement": {"value"},
    "RelationshipElement": {"first", "second"},
    "AnnotatedRelationshipElement": {"first", "second", "annotations"},
    "Entity": {"statements", "entityType", "globalAssetId", "specificAssetIds"},
    "BasicEventElement": {"observed"},
    "Operation": {"inputVariables", "outputVariables", "inoutputVariables"},
    "SubmodelElementCollection": {"value"},
    "SubmodelElementList": {"value"},
}


def metadata(element: Dict[str, Any]) -> Dict[str, Any]:
    exclude = _METADATA_EXCLUDE.get(element.get("modelType"), set())
    return {k: v for k, v in element.items() if k not in exclude}


# -----------------------------------------------------------------------------
# Reference ($reference)
# -----------------------------------------------------------------------------

def submodel_reference(submodel_id: str) -> Dict[str, Any]:
    return {
        "type": "ModelReference",
        "keys": [{"type": "Submodel", "value": submodel_id}],
    }


def element_reference(
    submodel_id: str,
    chain: List[Tuple[Dict[str, Any], str]],
) -> Dict[str, Any]:
    """ModelReference Submodel → ... → elemento (índice como valor em listas)."""
    reference = submodel_reference(submodel_id)
    reference["keys"].extend(
        {"type": element.get("modelType"), "value": key} for element, key in chain
    )
    return reference


# -----------------------------------------------------------------------------
# Path ($path)
# -----------------------------------------------------------------------------

def _descendant_paths(element: Dict[str, Any], path: str) -> Iterator[str]:
    for child, child_path in iter_children(element, path):
        yield child_path
        yield from _descendant_paths(child, child_path)


def element_paths(element: Dict[str, Any], path: str, deep: bool) -> List[str]:
    """
    idShortPath do elemento seguido dos filhos: todos os descendentes em
    level=deep, só os diretos em level=core.
    """
    if deep:
        return [path, *_descendant_paths(element, path)]
    return [path, *(child_path for _, child_path in iter_children(element, path))]


def top_level_paths(elements: List[Dict[str, Any]], deep: bool) -> List[str]:
    """
    Paths a partir dos elementos do topo de um submodelo. Eles já são os
    filhos diretos do nível requisitado: em core, só os próprios paths.
    """
    paths: List[str] = []
    for element in elements:
        path = element.get("idShort", "")
        paths.extend(element_paths(element, path, deep) if deep else [path])
    return paths

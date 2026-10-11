"""
Repositório em memória do modelo AAS servido pela API HTTP/REST.

A estrutura (metadados) vem do documento AAS V3 JSON original carregado pelo
parser — e não do dump pydantic, que acrescenta campos nulos e atributos fora
da spec. Os valores vivos ficam no address space OPC UA e são sobrepostos pelo
AASSerializer no momento da resposta.
"""
import copy
import json
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .encoding import b64url_decode
from .errors import BadRequestError, NotFoundError


# Atributo que guarda os filhos endereçáveis por idShortPath, por modelType
CHILDREN_BY_ID_SHORT = {
    "SubmodelElementCollection": "value",
    "Entity": "statements",
    "AnnotatedRelationshipElement": "annotations",
}
CHILDREN_BY_INDEX = {
    "SubmodelElementList": "value",
}

# Um segmento do idShortPath: idShort seguido de zero ou mais "[n]"
_SEGMENT = re.compile(r"^(?P<id_short>[A-Za-z][A-Za-z0-9_-]*)(?P<indexes>(\[\d+\])*)$")
_INDEX = re.compile(r"\[(\d+)\]")


def parse_id_short_path(id_short_path: str) -> List[Any]:
    """
    Converte "sme1.list[0][2].p1" em ["sme1", "list", 0, 2, "p1"].
    Strings são idShorts e inteiros são índices de SubmodelElementList.
    """
    if not id_short_path:
        raise BadRequestError("Empty idShortPath")

    tokens: List[Any] = []
    for segment in id_short_path.split("."):
        match = _SEGMENT.match(segment)
        # todo segmento começa com o idShort de um elemento; índices só o seguem
        if match is None or match.group("id_short") is None:
            raise BadRequestError(f"Invalid idShortPath: '{id_short_path}'")

        tokens.append(match.group("id_short"))
        tokens.extend(int(i) for i in _INDEX.findall(match.group("indexes")))

    return tokens


def join_path(parent: str, id_short: Optional[str] = None, index: Optional[int] = None) -> str:
    if index is not None:
        return f"{parent}[{index}]"
    return f"{parent}.{id_short}" if parent else str(id_short)


def iter_children(element: Dict[str, Any], path: str) -> Iterator[Tuple[Dict[str, Any], str]]:
    """Itera (filho, idShortPath do filho) de um SubmodelElement."""
    model_type = element.get("modelType")

    key = CHILDREN_BY_ID_SHORT.get(model_type)
    if key:
        for child in element.get(key) or []:
            yield child, join_path(path, id_short=child.get("idShort"))
        return

    key = CHILDREN_BY_INDEX.get(model_type)
    if key:
        for i, child in enumerate(element.get(key) or []):
            yield child, join_path(path, index=i)


def _reference_matches(reference: Optional[Dict[str, Any]], wanted: Any) -> bool:
    if not reference:
        return False

    keys = reference.get("keys") or []

    if isinstance(wanted, dict):
        wanted_keys = wanted.get("keys") or []
        return [(k.get("type"), k.get("value")) for k in keys] == [
            (k.get("type"), k.get("value")) for k in wanted_keys
        ]

    return any(k.get("value") == wanted for k in keys)


def decode_semantic_id(encoded: str) -> Any:
    """
    O parâmetro ?semanticId= é uma Reference serializada em JSON e
    codificada em base64url. Por tolerância, aceita também o valor puro
    da chave (ex.: um IRI) codificado em base64url.
    """
    decoded = b64url_decode(encoded, what="semanticId")
    try:
        parsed = json.loads(decoded)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return decoded


def has_semantic_id(element: Dict[str, Any], wanted: Any) -> bool:
    """?semanticId considera semanticId e supplementalSemanticIds."""
    if _reference_matches(element.get("semanticId"), wanted):
        return True
    return any(_reference_matches(r, wanted) for r in element.get("supplementalSemanticIds") or [])


def decode_specific_asset_id(encoded: str) -> Dict[str, Any]:
    """?assetIds=: cada item é um SpecificAssetId serializado em JSON e base64url."""
    decoded = b64url_decode(encoded, what="assetIds")
    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError as e:
        raise BadRequestError(f"Invalid assetIds item, expected a SpecificAssetId JSON: '{encoded}'") from e

    if not isinstance(parsed, dict) or "name" not in parsed or "value" not in parsed:
        raise BadRequestError(f"Invalid assetIds item, expected a SpecificAssetId JSON: '{encoded}'")
    return parsed


def _asset_id_pairs(shell: Dict[str, Any]) -> set:
    """Pares (name, value) de assetInformation; globalAssetId entra com o nome 'globalAssetId'."""
    info = shell.get("assetInformation") or {}
    pairs = {(sa.get("name"), sa.get("value")) for sa in info.get("specificAssetIds") or []}
    if info.get("globalAssetId"):
        pairs.add(("globalAssetId", info["globalAssetId"]))
    return pairs


def referenced_ids(node: Any) -> set:
    """Valores de todas as Keys de References contidas em uma estrutura JSON."""
    found = set()
    if isinstance(node, dict):
        if isinstance(node.get("keys"), list):
            found.update(k.get("value") for k in node["keys"] if isinstance(k, dict))
        for value in node.values():
            found |= referenced_ids(value)
    elif isinstance(node, list):
        for item in node:
            found |= referenced_ids(item)
    return found


class AASRepository:
    """Índices do Environment por identificador, preservando a ordem do modelo."""

    def __init__(self, document: Dict[str, Any]) -> None:
        self._document = copy.deepcopy(document)

        self._shells: Dict[str, Dict[str, Any]] = {
            s["id"]: s for s in self._document.get("assetAdministrationShells") or []
        }
        self._submodels: Dict[str, Dict[str, Any]] = {
            s["id"]: s for s in self._document.get("submodels") or []
        }
        self._concept_descriptions: Dict[str, Dict[str, Any]] = {
            c["id"]: c for c in self._document.get("conceptDescriptions") or []
        }

    # -------------------------------------------------------------------------
    # Asset Administration Shells
    # -------------------------------------------------------------------------

    def list_shells(
        self,
        id_short: Optional[str] = None,
        asset_ids: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        result = list(self._shells.values())

        if id_short is not None:
            result = [s for s in result if s.get("idShort") == id_short]

        if asset_ids:
            # todos os pares pedidos precisam existir na AAS (ordem irrelevante)
            wanted = {(a["name"], a["value"]) for a in asset_ids}
            result = [s for s in result if wanted <= _asset_id_pairs(s)]

        return result

    def get_shell(self, aas_id: str) -> Dict[str, Any]:
        shell = self._shells.get(aas_id)
        if shell is None:
            raise NotFoundError(f"AssetAdministrationShell with id '{aas_id}' not found")
        return shell

    def get_shell_submodel(self, aas_id: str, submodel_id: str) -> Dict[str, Any]:
        """Submodelo acessado pela AAS: precisa estar entre os submodel-refs dela."""
        shell = self.get_shell(aas_id)
        referenced = any(
            ref.get("keys") and ref["keys"][-1].get("value") == submodel_id
            for ref in shell.get("submodels") or []
        )
        if not referenced:
            raise NotFoundError(
                f"Submodel '{submodel_id}' is not referenced by AssetAdministrationShell '{aas_id}'"
            )
        return self.get_submodel(submodel_id)

    # -------------------------------------------------------------------------
    # Concept Descriptions
    # -------------------------------------------------------------------------

    def list_concept_descriptions(
        self,
        id_short: Optional[str] = None,
        is_case_of: Any = None,
        data_specification_ref: Any = None,
    ) -> List[Dict[str, Any]]:
        result = list(self._concept_descriptions.values())

        if id_short is not None:
            result = [c for c in result if c.get("idShort") == id_short]

        if is_case_of is not None:
            result = [
                c for c in result
                if any(_reference_matches(r, is_case_of) for r in c.get("isCaseOf") or [])
            ]

        if data_specification_ref is not None:
            result = [
                c for c in result
                if any(
                    _reference_matches(eds.get("dataSpecification"), data_specification_ref)
                    for eds in c.get("embeddedDataSpecifications") or []
                )
            ]

        return result

    def get_concept_description(self, cd_id: str) -> Dict[str, Any]:
        cd = self._concept_descriptions.get(cd_id)
        if cd is None:
            raise NotFoundError(f"ConceptDescription with id '{cd_id}' not found")
        return cd

    def referenced_concept_descriptions(self, roots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Concept Descriptions referenciadas direta ou indiretamente (ex.: valueList
        da IEC 61360, isCaseOf) pelos elementos dados, na ordem do modelo.
        """
        pending = referenced_ids(roots)
        selected: set = set()

        while pending:
            cd_id = pending.pop()
            cd = self._concept_descriptions.get(cd_id)
            if cd is None or cd_id in selected:
                continue
            selected.add(cd_id)
            pending |= referenced_ids(cd) - selected

        return [cd for cd_id, cd in self._concept_descriptions.items() if cd_id in selected]

    # -------------------------------------------------------------------------
    # Submodels
    # -------------------------------------------------------------------------

    def list_submodels(
        self,
        id_short: Optional[str] = None,
        semantic_id: Any = None,
    ) -> List[Dict[str, Any]]:
        result = list(self._submodels.values())

        if id_short is not None:
            result = [s for s in result if s.get("idShort") == id_short]

        if semantic_id is not None:
            result = [s for s in result if has_semantic_id(s, semantic_id)]

        return result

    def get_submodel(self, submodel_id: str) -> Dict[str, Any]:
        submodel = self._submodels.get(submodel_id)
        if submodel is None:
            raise NotFoundError(f"Submodel with id '{submodel_id}' not found")
        return submodel

    # -------------------------------------------------------------------------
    # Escrita — o editor monta o submodelo novo e troca o submodelo inteiro
    # -------------------------------------------------------------------------

    def has_submodel(self, submodel_id: str) -> bool:
        return submodel_id in self._submodels

    def put_submodel(self, submodel: Dict[str, Any]) -> None:
        """Insere ou substitui o submodelo (a posição de um existente é mantida)."""
        self._submodels[submodel["id"]] = submodel

    def delete_submodel(self, submodel_id: str) -> None:
        self.get_submodel(submodel_id)
        del self._submodels[submodel_id]

    def remove_submodel_reference(self, aas_id: str, submodel_id: str) -> None:
        shell = self.get_shell(aas_id)
        shell["submodels"] = [
            ref for ref in shell.get("submodels") or []
            if not (ref.get("keys") and ref["keys"][-1].get("value") == submodel_id)
        ]
        if not shell["submodels"]:
            # a Part 1 exige listas não vazias
            del shell["submodels"]

    def get_submodel_element(
        self,
        submodel_id: str,
        id_short_path: str,
    ) -> Dict[str, Any]:
        element, _ = self.get_submodel_element_chain(submodel_id, id_short_path)[-1]
        return element

    def get_submodel_element_chain(
        self,
        submodel_id: str,
        id_short_path: str,
    ) -> List[Tuple[Dict[str, Any], str]]:
        """
        Resolve o idShortPath e retorna a cadeia do primeiro elemento até o
        requisitado, como (elemento, valor da Key). O valor da Key é o idShort
        ou, para filhos de SubmodelElementList, o índice — como em uma
        ModelReference (Part 1).
        """
        submodel = self.get_submodel(submodel_id)
        tokens = parse_id_short_path(id_short_path)

        not_found = NotFoundError(
            f"SubmodelElement with idShortPath '{id_short_path}' "
            f"not found in Submodel '{submodel_id}'"
        )

        chain: List[Tuple[Dict[str, Any], str]] = []
        children: List[Dict[str, Any]] = submodel.get("submodelElements") or []
        by_index = False

        for token in tokens:
            if isinstance(token, int):
                if not by_index or token >= len(children):
                    raise not_found
                current = children[token]

            else:
                if by_index:
                    raise not_found
                current = next((c for c in children if c.get("idShort") == token), None)
                if current is None:
                    raise not_found

            chain.append((current, str(token)))

            model_type = current.get("modelType")
            if model_type in CHILDREN_BY_INDEX:
                children = current.get(CHILDREN_BY_INDEX[model_type]) or []
                by_index = True
            else:
                children = current.get(CHILDREN_BY_ID_SHORT.get(model_type, ""), None) or []
                by_index = False

        return chain

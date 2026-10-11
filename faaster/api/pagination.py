"""
Paginação por cursor (IDTA-01002-3-2 §Pagination).

O cursor é opaco para o cliente; aqui ele carrega o offset do próximo item
codificado em base64url. A ordem é determinística: a ordem do modelo AAS.
"""
from typing import Any, Dict, List, Optional, Sequence, TypeVar

from .encoding import b64url_decode, b64url_encode
from .errors import BadRequestError

T = TypeVar("T")

DEFAULT_LIMIT = 100


def _decode_cursor(cursor: str) -> int:
    decoded = b64url_decode(cursor, what="cursor")
    if not decoded.isdigit():
        raise BadRequestError(f"Invalid cursor: '{cursor}'")
    return int(decoded)


def paginate(
    items: Sequence[T],
    limit: Optional[int],
    cursor: Optional[str],
) -> tuple[List[T], Optional[str]]:
    """Retorna (página, cursor da próxima página ou None no fim)."""
    if cursor is not None and cursor == "":
        # Constraint AASa-001: cursor vazio é inválido
        raise BadRequestError("The cursor query parameter must not be empty")

    start = _decode_cursor(cursor) if cursor else 0
    size = limit if limit is not None else DEFAULT_LIMIT
    end = start + size

    page = list(items[start:end])
    next_cursor = b64url_encode(str(end)) if end < len(items) else None
    return page, next_cursor


def paged_result(result: List[Any], next_cursor: Optional[str]) -> Dict[str, Any]:
    paging_metadata: Dict[str, Any] = {}
    if next_cursor:
        paging_metadata["cursor"] = next_cursor
    return {"paging_metadata": paging_metadata, "result": result}

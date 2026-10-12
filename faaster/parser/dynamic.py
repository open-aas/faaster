"""
Marcação de variáveis dinâmicas (decisão D3 da proposta de dissertação).

Uma Property é dinâmica (valor atualizado pela extensão e elegível a HDA) quando tem o
Qualifier ``faaster:dynamic`` com valor verdadeiro. ``category: VARIABLE``, usado antes,
foi descontinuado na v3.1 do metamodelo (IDTA-01001) e continua aceito com aviso.
"""
from __future__ import annotations

from typing import Any

DYNAMIC_QUALIFIER = "faaster:dynamic"
LEGACY_CATEGORY = "VARIABLE"
_TRUE = {"true", "1"}


def is_dynamic(element: Any) -> tuple[bool, bool]:
    """Retorna ``(dinâmica, via_category_descontinuada)``."""
    for qualifier in getattr(element, "qualifiers", None) or []:
        if getattr(qualifier, "type", None) == DYNAMIC_QUALIFIER:
            return str(getattr(qualifier, "value", "")).strip().lower() in _TRUE, False
    if getattr(element, "category", None) == LEGACY_CATEGORY:
        return True, True
    return False, False

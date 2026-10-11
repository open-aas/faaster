"""
Codificação de identificadores na API HTTP/REST (IDTA-01002-3-2 §Addressing Resources).

Identificadores de Identifiables (AAS, Submodel, ConceptDescription) trafegam
na URL como base64url do texto UTF-8, sem padding ('=').
"""
import base64
import binascii
import re

from .errors import BadRequestError


_ALPHABET = re.compile(r"[A-Za-z0-9_-]+={0,2}")


def b64url_encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def b64url_decode(value: str, what: str = "identifier") -> str:
    """
    Decodifica base64url tolerando a ausência de padding (exigida pela spec)
    e também clientes que ainda enviam '='.
    """
    # urlsafe_b64decode descarta caracteres fora do alfabeto em silêncio
    if not _ALPHABET.fullmatch(value):
        raise BadRequestError(f"Invalid base64url-encoded {what}: '{value}'")

    try:
        padded = value + "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")

    except (binascii.Error, UnicodeError, ValueError) as e:
        raise BadRequestError(f"Invalid base64url-encoded {what}: '{value}'") from e

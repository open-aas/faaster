"""
Erros da API HTTP/REST e o objeto Result da spec
(IDTA-01002-3-2 §Status Code, Error Handling & Result Messages).

Toda resposta de erro carrega um Result:
    {"messages": [{"code": "404", "messageType": "Error", "text": "...", "timestamp": "..."}]}
"""
from datetime import datetime, timezone
from typing import Any, Dict


class ApiError(Exception):
    """Erro mapeado para um status HTTP com corpo Result."""

    status_code: int = 500

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text


class BadRequestError(ApiError):
    status_code = 400


class NotFoundError(ApiError):
    status_code = 404


class ConflictError(ApiError):
    status_code = 409


class MethodNotAllowedError(ApiError):
    status_code = 405


class NotImplementedApiError(ApiError):
    status_code = 501


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def message(code: str, text: str, message_type: str = "Error") -> Dict[str, Any]:
    return {
        "code": code,
        "messageType": message_type,
        "text": text,
        "timestamp": _timestamp(),
    }


def result_body(status_code: int, text: str, message_type: str = "Error") -> Dict[str, Any]:
    return {"messages": [message(str(status_code), text, message_type)]}

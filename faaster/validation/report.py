"""Relatório estruturado da validação (etapas do pipeline da proposta, §5.6)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, List, Optional


def faaster_version() -> str:
    """Installed version, else the repository's pyproject.toml (images install --no-root)."""
    try:
        return version("faaster")
    except PackageNotFoundError:
        pass
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(), re.MULTILINE)
    except OSError:
        match = None
    return match.group(1) if match else "unknown"


@dataclass
class Issue:
    severity: str  # "error" | "warning"
    message: str
    path: Optional[str] = None

    def to_dict(self) -> dict:
        data = {"severity": self.severity, "message": self.message}
        if self.path:
            data["path"] = self.path
        return data


@dataclass
class Stage:
    number: int
    name: str
    blocking: bool
    issues: List[Issue] = field(default_factory=list)
    skipped: bool = False

    def error(self, message: str, path: Optional[str] = None) -> None:
        # Etapas não bloqueantes registram seus achados como aviso.
        severity = "error" if self.blocking else "warning"
        self.issues.append(Issue(severity, message, path))

    def warning(self, message: str, path: Optional[str] = None) -> None:
        self.issues.append(Issue("warning", message, path))

    @property
    def failed(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def status(self) -> str:
        if self.skipped:
            return "skipped"
        if self.failed:
            return "failed"
        return "warning" if self.issues else "passed"

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "name": self.name,
            "blocking": self.blocking,
            "status": self.status,
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass
class Report:
    stages: List[Stage]

    @property
    def ok(self) -> bool:
        return not any(s.failed for s in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "faaster_version": faaster_version(),
            "ok": self.ok,
            "stages": [s.to_dict() for s in self.stages],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_text(self) -> str:
        lines = []
        for s in self.stages:
            lines.append(f"[{s.status:>7}] stage {s.number} {s.name}")
            lines += [f"          {i.severity}: {i.message}" for i in s.issues]
        lines.append("OK" if self.ok else "FAILED")
        return "\n".join(lines)

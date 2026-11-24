"""Validação do modelo AAS e das extensões antes da implantação (decisão D15)."""
from .report import Issue, Report, Stage
from .validator import validate

__all__ = ["Issue", "Report", "Stage", "validate"]

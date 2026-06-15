from .policies import (
    extract_policy,
    AggregationPolicy,
    HDAMode,
    HDAFunction,
    has_hda_policy,
)


def __getattr__(name: str):
    if name == "HDAManager":
        from .manager import HDAManager
        return HDAManager
    if name == "HDAManagerFactory":
        from .factory import HDAManagerFactory
        return HDAManagerFactory
    if name in ("TimescaleHDAStorage", "build_index", "build_table_name"):
        from .storage import build_index, build_table_name, TimescaleHDAStorage
        globals()["build_index"] = build_index
        globals()["build_table_name"] = build_table_name
        globals()["TimescaleHDAStorage"] = TimescaleHDAStorage
        return globals()[name]
    raise AttributeError(f"module 'faaster.hda' has no attribute {name!r}")


__all__ = [
    "HDAManager",
    "HDAManagerFactory",
    "AggregationPolicy",
    "HDAMode",
    "HDAFunction",
    "extract_policy",
    "has_hda_policy",
    "TimescaleHDAStorage",
    "build_index",
    "build_table_name",
]

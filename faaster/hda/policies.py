from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class HDAMode(str, Enum):
    sample    = "sample"
    aggregate = "aggregate"


class HDAFunction(str, Enum):
    mean = "mean"
    sum  = "sum"
    max  = "max"
    min  = "min"
    last = "last"


_WINDOW_SECONDS = {
    "1min":  60,
    "5min":  300,
    "10min": 600,
    "15min": 900,
    "1hour": 3600,
    "1day":  86400,
}

_DEFAULT_LEVELS = ["1min", "1hour", "1day"]

_DEFAULT_RETENTION = {
    "raw":   "30 days",
    "1min":  "1 year",
    "1hour": "5 years",
    "1day":  None,
}


@dataclass
class AggregationPolicy:
    """
    Define como o HDA deve armazenar e agregar os dados
    de uma variável AAS.

    Modo sample:
        Cada valor recebido é persistido na hypertable raw.
        Continuous aggregates são criados para cada level.

        Exemplo — Voltage a 1Hz:
            raw   → cada leitura por segundo
            1min  → média/max/min por minuto
            1hour → média/max/min por hora
            1day  → média/max/min por dia

    Modo aggregate:
        Valores são acumulados em buffer em memória.
        Ao final da janela, o agregado é calculado e persistido.
        Sem continuous aggregates — o dado já chega agregado.

        Exemplo — ActiveEnergy com janela de 15min (ANEEL):
            buffer acumula amostras por 15min
            → calcula mean/sum/etc
            → persiste 1 registro por janela
    """

    mode: HDAMode = HDAMode.sample

    # --- modo sample ---
    levels: List[str] = field(
        default_factory=lambda: list(_DEFAULT_LEVELS)
    )
    retention: Dict[str, Optional[str]] = field(
        default_factory=lambda: dict(_DEFAULT_RETENTION)
    )
    sample_interval_seconds: Optional[int] = None

    # --- modo aggregate ---
    window: Optional[str] = None
    function: HDAFunction = HDAFunction.mean
    retention_aggregate: Optional[str] = "5 years"

    @property
    def window_seconds(self) -> Optional[int]:
        """Converte a janela de agregação para segundos."""
        if self.window is None:
            return None
        return _WINDOW_SECONDS.get(self.window)

    @property
    def is_sample(self) -> bool:
        return self.mode == HDAMode.sample

    @property
    def is_aggregate(self) -> bool:
        return self.mode == HDAMode.aggregate


def has_hda_policy(extensions: Optional[list]) -> bool:
    """
    Retorna True apenas se existir pelo menos uma
    extension faaster:hda:* no elemento.
    """
    if not extensions:
        return False
    return any(
        ext.name and ext.name.startswith("faaster:hda:")
        for ext in extensions
    )


def extract_policy(extensions: Optional[list]) -> Optional[AggregationPolicy]:
    """
    Extrai a AggregationPolicy das extensions do metamodelo AAS V3.

    Extensions reconhecidas (prefixo faaster:hda:):

    Modo sample:
        faaster:hda:mode              → "sample" (padrão)
        faaster:hda:levels            → "1min,1hour,1day"
        faaster:hda:sample_interval   → "1" (segundos)
        faaster:hda:retention:raw     → "30 days"
        faaster:hda:retention:1min    → "1 year"
        faaster:hda:retention:1hour   → "5 years"
        faaster:hda:retention:1day    → None (sem expiração)

    Modo aggregate:
        faaster:hda:mode              → "aggregate"
        faaster:hda:window            → "15min"
        faaster:hda:function          → "mean" | "sum" | "max" | "min" | "last"
        faaster:hda:retention         → "5 years"

    Exemplo de modelagem no AAS:
        {
            "idShort": "Voltage",
            "category": "VARIABLE",
            "extensions": [
                {
                    "name": "faaster:hda:mode",
                    "valueType": "xs:string",
                    "value": "sample"
                },
                {
                    "name": "faaster:hda:levels",
                    "valueType": "xs:string",
                    "value": "1min,1hour,1day"
                },
                {
                    "name": "faaster:hda:retention:raw",
                    "valueType": "xs:string",
                    "value": "7 days"
                }
            ]
        }

        {
            "idShort": "ActiveEnergy",
            "category": "VARIABLE",
            "extensions": [
                {
                    "name": "faaster:hda:mode",
                    "valueType": "xs:string",
                    "value": "aggregate"
                },
                {
                    "name": "faaster:hda:window",
                    "valueType": "xs:string",
                    "value": "15min"
                },
                {
                    "name": "faaster:hda:function",
                    "valueType": "xs:string",
                    "value": "mean"
                },
                {
                    "name": "faaster:hda:retention",
                    "valueType": "xs:string",
                    "value": "5 years"
                }
            ]
        }

    Retorna AggregationPolicy com defaults se nenhuma
    extension faaster:hda:* for encontrada.
    """
    if not has_hda_policy(extensions):
        return None

    ext_map = {
        ext.name: ext.value
        for ext in extensions
        if ext.name and ext.name.startswith("faaster:hda:")
    }

    mode = HDAMode(ext_map.get("faaster:hda:mode", HDAMode.sample.value))

    if mode == HDAMode.aggregate:
        return _extract_aggregate_policy(ext_map)

    return _extract_sample_policy(ext_map)


def _extract_sample_policy(ext_map: Dict[str, str]) -> AggregationPolicy:
    levels_raw = ext_map.get("faaster:hda:levels", ",".join(_DEFAULT_LEVELS))
    levels = [l.strip() for l in levels_raw.split(",") if l.strip()]

    sample_interval = ext_map.get("faaster:hda:sample_interval")

    retention: Dict[str, Optional[str]] = {}
    for level in ["raw"] + levels:
        key = f"faaster:hda:retention:{level}"
        if key in ext_map:
            value = ext_map[key]
            retention[level] = value if value.lower() != "none" else None
        else:
            retention[level] = _DEFAULT_RETENTION.get(level)

    return AggregationPolicy(
        mode=HDAMode.sample,
        levels=levels,
        retention=retention,
        sample_interval_seconds=int(sample_interval) if sample_interval else None,
    )


def _extract_aggregate_policy(ext_map: Dict[str, str]) -> AggregationPolicy:
    window = ext_map.get("faaster:hda:window")

    if window and window not in _WINDOW_SECONDS:
        raise ValueError(
            f"Invalid faaster:hda:window value: '{window}'. "
            f"Supported: {list(_WINDOW_SECONDS.keys())}"
        )

    function_raw = ext_map.get("faaster:hda:function", HDAFunction.mean.value)
    try:
        function = HDAFunction(function_raw)
    except ValueError:
        raise ValueError(
            f"Invalid faaster:hda:function value: '{function_raw}'. "
            f"Supported: {[f.value for f in HDAFunction]}"
        )

    retention_raw = ext_map.get("faaster:hda:retention", "5 years")
    retention = retention_raw if retention_raw.lower() != "none" else None

    return AggregationPolicy(
        mode=HDAMode.aggregate,
        window=window,
        function=function,
        retention_aggregate=retention,
    )

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Dict, List, Optional

import re


class HDAMode(str, Enum):
    sample    = "sample"
    aggregate = "aggregate"


class HDAFunction(str, Enum):
    mean = "mean"
    sum  = "sum"
    max  = "max"
    min  = "min"
    last = "last"


WINDOW_SECONDS = {
    "1min":  60,
    "5min":  300,
    "10min": 600,
    "15min": 900,
    "1hour": 3600,
    "1day":  86400,
}

# janela de atualização do continuous aggregate de cada level (sempre sobre a
# hypertable raw). Só buckets completos dentro da janela são materializados e o
# TimescaleDB exige que ela cubra ao menos dois buckets; o trecho mais recente,
# ainda não materializado, é completado em tempo real na consulta.
@dataclass(frozen=True)
class LevelRefresh:
    start_offset: timedelta
    end_offset: timedelta
    schedule_interval: timedelta


LEVEL_REFRESH: Dict[str, LevelRefresh] = {
    "1min":  LevelRefresh(timedelta(minutes=10), timedelta(minutes=1), timedelta(minutes=1)),
    "5min":  LevelRefresh(timedelta(minutes=30), timedelta(minutes=1), timedelta(minutes=5)),
    "10min": LevelRefresh(timedelta(hours=1),    timedelta(minutes=1), timedelta(minutes=10)),
    "15min": LevelRefresh(timedelta(hours=1),    timedelta(minutes=1), timedelta(minutes=15)),
    "1hour": LevelRefresh(timedelta(hours=4),    timedelta(minutes=1), timedelta(hours=1)),
    "1day":  LevelRefresh(timedelta(days=4),     timedelta(minutes=1), timedelta(hours=1)),
}

_DEFAULT_LEVELS = ["1min", "1hour", "1day"]

_RETENTION_PATTERN = re.compile(r"^(\d+)\s*(minute|hour|day|week|month|year)s?$", re.IGNORECASE)

_UNIT_SECONDS = {
    "minute": 60,
    "hour":   3600,
    "day":    86400,
    "week":   7 * 86400,
    "month":  30 * 86400,
    "year":   365 * 86400,
}

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
        Continuous aggregates são criados para cada level, todos
        calculados direto da raw (max/min/stddev/count exatos e
        levels independentes entre si).

        Exemplo — Voltage a 1Hz:
            raw   → cada leitura por segundo
            1min  → média/max/min por minuto
            1hour → média/max/min por hora
            1day  → média/max/min por dia

    Modo aggregate:
        Valores são acumulados em buffer em memória, por janela
        alinhada ao relógio (UTC: 15min fecha em :00/:15/:30/:45).
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
        return WINDOW_SECONDS.get(self.window)

    @property
    def is_sample(self) -> bool:
        return self.mode == HDAMode.sample

    @property
    def is_aggregate(self) -> bool:
        return self.mode == HDAMode.aggregate


def parse_retention(value: Optional[str], key: str) -> Optional[str]:
    """
    Normaliza uma retenção "<n> <unidade>" (minute, hour, day, week, month,
    year, no singular ou plural). "none" (ou ausente) → sem expiração.
    """
    if value is None or value.strip().lower() == "none":
        return None

    match = _RETENTION_PATTERN.match(value.strip())
    if match is None or int(match.group(1)) == 0:
        raise ValueError(
            f"Invalid {key} value: '{value}'. "
            "Expected '<n> <minute|hour|day|week|month|year>[s]' or 'none'"
        )

    amount, unit = int(match.group(1)), match.group(2).lower()
    return f"{amount} {unit}" if amount == 1 else f"{amount} {unit}s"


def retention_seconds(retention: str) -> int:
    """Duração aproximada (mês = 30 dias, ano = 365 dias) de uma retenção normalizada."""
    amount, unit = retention.split()
    return int(amount) * _UNIT_SECONDS[unit.rstrip("s")]


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
                                        (1min, 5min, 10min, 15min, 1hour, 1day)
        faaster:hda:sample_interval   → "1" (segundos)
        faaster:hda:retention:raw     → "30 days"
        faaster:hda:retention:1min    → "1 year"
        faaster:hda:retention:1hour   → "5 years"
        faaster:hda:retention:1day    → None (sem expiração)

    Modo aggregate:
        faaster:hda:mode              → "aggregate"
        faaster:hda:window            → "15min" (obrigatório)
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

    Retenções: "<n> <minute|hour|day|week|month|year>[s]" ou "none".

    Retorna None se nenhuma extension faaster:hda:* for encontrada.
    Lança ValueError para valores inválidos.
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
    levels: List[str] = []
    for level in (l.strip() for l in levels_raw.split(",")):
        if not level or level in levels:
            continue
        if level not in LEVEL_REFRESH:
            raise ValueError(
                f"Invalid faaster:hda:levels value: '{level}'. "
                f"Supported: {list(LEVEL_REFRESH.keys())}"
            )
        levels.append(level)

    sample_interval = ext_map.get("faaster:hda:sample_interval")

    retention: Dict[str, Optional[str]] = {}
    for level in ["raw"] + levels:
        key = f"faaster:hda:retention:{level}"
        if key in ext_map:
            retention[level] = parse_retention(ext_map[key], key)
        else:
            retention[level] = _DEFAULT_RETENTION.get(level)

    _check_refresh_windows(levels, retention)

    return AggregationPolicy(
        mode=HDAMode.sample,
        levels=levels,
        retention=retention,
        sample_interval_seconds=int(sample_interval) if sample_interval else None,
    )


def _check_refresh_windows(levels: List[str], retention: Dict[str, Optional[str]]) -> None:
    """
    O continuous aggregate de um level é recalculado a partir da hypertable raw
    dentro da sua janela de atualização: se a retenção já tiver apagado esses
    dados raw, o TimescaleDB apaga também os buckets agregados correspondentes.
    """
    for level in levels:
        window = LEVEL_REFRESH[level].start_offset.total_seconds()

        for owner in ("raw", level):
            kept = retention.get(owner)
            if kept is not None and retention_seconds(kept) <= window:
                raise ValueError(
                    f"Invalid faaster:hda:retention:{owner} value: '{kept}'. "
                    f"Level '{level}' is refreshed from the last "
                    f"{LEVEL_REFRESH[level].start_offset} of raw data, so the "
                    f"retention must be longer than that"
                )


def _extract_aggregate_policy(ext_map: Dict[str, str]) -> AggregationPolicy:
    window = ext_map.get("faaster:hda:window")

    if window is None:
        raise ValueError(
            "faaster:hda:window is required in aggregate mode. "
            f"Supported: {list(WINDOW_SECONDS.keys())}"
        )

    if window not in WINDOW_SECONDS:
        raise ValueError(
            f"Invalid faaster:hda:window value: '{window}'. "
            f"Supported: {list(WINDOW_SECONDS.keys())}"
        )

    function_raw = ext_map.get("faaster:hda:function", HDAFunction.mean.value)
    try:
        function = HDAFunction(function_raw)
    except ValueError:
        raise ValueError(
            f"Invalid faaster:hda:function value: '{function_raw}'. "
            f"Supported: {[f.value for f in HDAFunction]}"
        )

    retention = parse_retention(ext_map.get("faaster:hda:retention", "5 years"), "faaster:hda:retention")

    return AggregationPolicy(
        mode=HDAMode.aggregate,
        window=window,
        function=function,
        retention_aggregate=retention,
    )

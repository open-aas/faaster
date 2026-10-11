from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import asyncio
import statistics

from .policies import HDAFunction


# resultados de janelas cujo insert falhou, guardados para nova tentativa;
# acima disso os mais antigos são descartados (banco fora do ar por muito tempo)
MAX_PENDING_RESULTS = 10_000


def bucket_start(timestamp: datetime, window_seconds: int) -> datetime:
    """Início da janela alinhada ao relógio (UTC) que contém o timestamp."""
    epoch = timestamp.timestamp()
    return datetime.fromtimestamp(epoch - epoch % window_seconds, tz=timezone.utc)


@dataclass(frozen=True)
class WindowResult:
    """Agregado de uma janela, pronto para persistir."""
    bucket: datetime
    value: float
    sample_count: int
    last_timestamp: datetime


def compute(
    bucket: datetime,
    samples: List[Tuple[datetime, float]],
    function: HDAFunction,
) -> WindowResult:
    values = [value for _, value in samples]
    last_timestamp, last_value = max(samples, key=lambda sample: sample[0])

    if function == HDAFunction.sum:
        value = sum(values)
    elif function == HDAFunction.max:
        value = max(values)
    elif function == HDAFunction.min:
        value = min(values)
    elif function == HDAFunction.last:
        value = last_value
    else:
        value = statistics.fmean(values)

    return WindowResult(
        bucket=bucket,
        value=float(value),
        sample_count=len(values),
        last_timestamp=last_timestamp,
    )


@dataclass
class AggregateBuffer:
    """
    Buffer em memória para o modo aggregate.
    Usado apenas quando AggregationPolicy.mode == aggregate.

    As amostras são agrupadas pela janela a que pertencem (pelo seu
    timestamp), não pelo momento em que chegaram: uma amostra atrasada de
    uma janela já persistida vira um novo agregado da mesma janela, que o
    banco combina com o já gravado.
    """
    buckets: Dict[datetime, List[Tuple[datetime, float]]] = field(default_factory=dict)
    pending: List[WindowResult] = field(default_factory=list)
    task: Optional[asyncio.Task] = None

    def push(self, value: float, timestamp: datetime, window_seconds: int) -> None:
        bucket = bucket_start(timestamp, window_seconds)
        self.buckets.setdefault(bucket, []).append((timestamp, value))

    def take_closed(
        self,
        now: datetime,
        window_seconds: int,
        function: HDAFunction,
    ) -> List[WindowResult]:
        """
        Remove e devolve os agregados das janelas já encerradas, junto com os
        que aguardavam nova tentativa. Síncrono: amostras que chegarem enquanto
        o resultado é gravado vão para o buffer e não se perdem.
        """
        closed = sorted(
            bucket for bucket in self.buckets
            if bucket.timestamp() + window_seconds <= now.timestamp()
        )
        results = self.pending + [
            compute(bucket, self.buckets.pop(bucket), function) for bucket in closed
        ]
        self.pending = []
        return results

    def take_all(self, function: HDAFunction) -> List[WindowResult]:
        """Como take_closed, incluindo a janela em aberto (encerramento do servidor)."""
        results = self.pending + [
            compute(bucket, self.buckets.pop(bucket), function) for bucket in sorted(self.buckets)
        ]
        self.pending = []
        return results

    def retry(self, results: List[WindowResult]) -> int:
        """Guarda resultados não gravados; devolve quantos foram descartados."""
        self.pending = results + self.pending
        dropped = max(0, len(self.pending) - MAX_PENDING_RESULTS)
        if dropped:
            self.pending = self.pending[dropped:]
        return dropped

    @property
    def is_empty(self) -> bool:
        return not self.buckets and not self.pending

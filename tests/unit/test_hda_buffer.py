"""
Buffer do modo aggregate: janelas alinhadas ao relógio, agregados exatos e
retentativa sem perder amostras.
"""
from datetime import datetime, timedelta, timezone

import pytest

from faaster.hda.buffer import (
    MAX_PENDING_RESULTS,
    AggregateBuffer,
    WindowResult,
    bucket_start,
    compute,
)
from faaster.hda.policies import HDAFunction


T0 = datetime(2026, 10, 11, 10, 0, tzinfo=timezone.utc)
WINDOW = 900  # 15min


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


@pytest.mark.parametrize("timestamp, window, expected", [
    (at(7.5), 900, at(0)),
    (at(15), 900, at(15)),
    (at(44.99), 900, at(30)),
    (at(59), 3600, at(0)),
    (datetime(2026, 10, 11, 23, 59, tzinfo=timezone.utc), 86400, datetime(2026, 10, 11, tzinfo=timezone.utc)),
])
def test_bucket_start_is_aligned_to_the_clock(timestamp, window, expected):
    assert bucket_start(timestamp, window) == expected


def test_bucket_start_accepts_other_timezones():
    brasilia = timezone(timedelta(hours=-3))
    local = datetime(2026, 10, 11, 7, 20, tzinfo=brasilia)  # 10:20 UTC
    assert bucket_start(local, WINDOW) == at(15)


SAMPLES = [(at(1), 4.0), (at(3), 1.0), (at(2), 10.0)]


@pytest.mark.parametrize("function, value", [
    (HDAFunction.mean, 5.0),
    (HDAFunction.sum, 15.0),
    (HDAFunction.max, 10.0),
    (HDAFunction.min, 1.0),
    (HDAFunction.last, 1.0),  # maior timestamp, não a última a chegar
])
def test_compute(function, value):
    result = compute(at(0), SAMPLES, function)

    assert result == WindowResult(bucket=at(0), value=value, sample_count=3, last_timestamp=at(3))


def test_samples_are_grouped_by_their_own_timestamp():
    buffer = AggregateBuffer()
    buffer.push(1.0, at(1), WINDOW)
    buffer.push(2.0, at(16), WINDOW)
    buffer.push(3.0, at(14), WINDOW)  # chega depois, mas pertence à primeira janela

    assert sorted(buffer.buckets) == [at(0), at(15)]
    assert [v for _, v in buffer.buckets[at(0)]] == [1.0, 3.0]


def test_take_closed_keeps_open_window():
    buffer = AggregateBuffer()
    buffer.push(1.0, at(1), WINDOW)
    buffer.push(3.0, at(2), WINDOW)
    buffer.push(7.0, at(16), WINDOW)

    results = buffer.take_closed(at(20), WINDOW, HDAFunction.sum)

    assert [(r.bucket, r.value, r.sample_count) for r in results] == [(at(0), 4.0, 2)]
    assert list(buffer.buckets) == [at(15)]


def test_window_closes_exactly_at_its_end():
    buffer = AggregateBuffer()
    buffer.push(1.0, at(1), WINDOW)

    assert buffer.take_closed(at(14.99), WINDOW, HDAFunction.mean) == []
    assert len(buffer.take_closed(at(15), WINDOW, HDAFunction.mean)) == 1


def test_late_sample_becomes_new_result_for_same_window():
    buffer = AggregateBuffer()
    buffer.push(1.0, at(1), WINDOW)
    buffer.take_closed(at(16), WINDOW, HDAFunction.sum)

    buffer.push(5.0, at(14), WINDOW)
    [late] = buffer.take_closed(at(30), WINDOW, HDAFunction.sum)

    # o banco combina com o agregado já gravado da janela
    assert (late.bucket, late.value, late.sample_count) == (at(0), 5.0, 1)


def test_retry_returns_results_in_next_take():
    buffer = AggregateBuffer()
    buffer.push(1.0, at(1), WINDOW)
    failed = buffer.take_closed(at(16), WINDOW, HDAFunction.sum)

    assert buffer.retry(failed) == 0
    buffer.push(2.0, at(20), WINDOW)
    results = buffer.take_closed(at(31), WINDOW, HDAFunction.sum)

    assert [r.bucket for r in results] == [at(0), at(15)]
    assert buffer.is_empty


def test_retry_drops_oldest_beyond_limit():
    buffer = AggregateBuffer()
    results = [
        WindowResult(bucket=at(15 * i), value=1.0, sample_count=1, last_timestamp=at(15 * i))
        for i in range(MAX_PENDING_RESULTS + 2)
    ]

    assert buffer.retry(results) == 2
    assert buffer.pending[0].bucket == at(30)


def test_take_all_includes_open_window():
    buffer = AggregateBuffer()
    buffer.push(1.0, at(1), WINDOW)
    buffer.push(2.0, at(16), WINDOW)

    results = buffer.take_all(HDAFunction.max)

    assert [(r.bucket, r.value) for r in results] == [(at(0), 1.0), (at(15), 2.0)]
    assert buffer.is_empty

import pytest
from types import SimpleNamespace
from faaster.hda.policies import (
    HDAMode,
    HDAFunction,
    AggregationPolicy,
    extract_policy,
    has_hda_policy,
)


def ext(name, value):
    return SimpleNamespace(name=name, value=value)


# ------------------------------------------------------------------
# has_hda_policy
# ------------------------------------------------------------------

def test_has_hda_policy_empty():
    assert has_hda_policy([]) is False


def test_has_hda_policy_none():
    assert has_hda_policy(None) is False


def test_has_hda_policy_true():
    exts = [ext("faaster:hda:mode", "sample")]
    assert has_hda_policy(exts) is True


def test_has_hda_policy_ignores_other_prefixes():
    exts = [ext("other:ext", "value")]
    assert has_hda_policy(exts) is False


# ------------------------------------------------------------------
# extract_policy — retorna None sem extensions hda
# ------------------------------------------------------------------

def test_extract_policy_no_extensions():
    assert extract_policy([]) is None


def test_extract_policy_none():
    assert extract_policy(None) is None


def test_extract_policy_non_hda_extensions():
    exts = [ext("semantic:id", "urn:something")]
    assert extract_policy(exts) is None


# ------------------------------------------------------------------
# Modo sample — defaults
# ------------------------------------------------------------------

def test_sample_mode_defaults():
    exts = [ext("faaster:hda:mode", "sample")]
    policy = extract_policy(exts)
    assert policy.mode == HDAMode.sample
    assert policy.levels == ["1min", "1hour", "1day"]
    assert policy.sample_interval_seconds is None


def test_sample_mode_is_sample_property():
    exts = [ext("faaster:hda:mode", "sample")]
    policy = extract_policy(exts)
    assert policy.is_sample is True
    assert policy.is_aggregate is False


def test_sample_mode_custom_levels():
    exts = [
        ext("faaster:hda:mode", "sample"),
        ext("faaster:hda:levels", "1min,5min"),
    ]
    policy = extract_policy(exts)
    assert policy.levels == ["1min", "5min"]


def test_sample_mode_custom_retention():
    exts = [
        ext("faaster:hda:mode", "sample"),
        ext("faaster:hda:retention:raw", "7 days"),
    ]
    policy = extract_policy(exts)
    assert policy.retention["raw"] == "7 days"


def test_sample_mode_retention_none_string():
    exts = [
        ext("faaster:hda:mode", "sample"),
        ext("faaster:hda:retention:1day", "none"),
    ]
    policy = extract_policy(exts)
    assert policy.retention["1day"] is None


def test_sample_mode_sample_interval():
    exts = [
        ext("faaster:hda:mode", "sample"),
        ext("faaster:hda:sample_interval", "5"),
    ]
    policy = extract_policy(exts)
    assert policy.sample_interval_seconds == 5


# ------------------------------------------------------------------
# Modo aggregate
# ------------------------------------------------------------------

def test_aggregate_mode_basic():
    exts = [
        ext("faaster:hda:mode", "aggregate"),
        ext("faaster:hda:window", "15min"),
        ext("faaster:hda:function", "mean"),
    ]
    policy = extract_policy(exts)
    assert policy.mode == HDAMode.aggregate
    assert policy.window == "15min"
    assert policy.function == HDAFunction.mean


def test_aggregate_mode_is_aggregate_property():
    exts = [
        ext("faaster:hda:mode", "aggregate"),
        ext("faaster:hda:window", "1hour"),
    ]
    policy = extract_policy(exts)
    assert policy.is_aggregate is True
    assert policy.is_sample is False


def test_aggregate_window_seconds():
    exts = [
        ext("faaster:hda:mode", "aggregate"),
        ext("faaster:hda:window", "15min"),
    ]
    policy = extract_policy(exts)
    assert policy.window_seconds == 900


def test_aggregate_window_1hour_seconds():
    exts = [
        ext("faaster:hda:mode", "aggregate"),
        ext("faaster:hda:window", "1hour"),
    ]
    policy = extract_policy(exts)
    assert policy.window_seconds == 3600


def test_aggregate_function_sum():
    exts = [
        ext("faaster:hda:mode", "aggregate"),
        ext("faaster:hda:window", "15min"),
        ext("faaster:hda:function", "sum"),
    ]
    policy = extract_policy(exts)
    assert policy.function == HDAFunction.sum


def test_aggregate_custom_retention():
    exts = [
        ext("faaster:hda:mode", "aggregate"),
        ext("faaster:hda:window", "15min"),
        ext("faaster:hda:retention", "10 years"),
    ]
    policy = extract_policy(exts)
    assert policy.retention_aggregate == "10 years"


def test_aggregate_retention_none_string():
    exts = [
        ext("faaster:hda:mode", "aggregate"),
        ext("faaster:hda:window", "15min"),
        ext("faaster:hda:retention", "none"),
    ]
    policy = extract_policy(exts)
    assert policy.retention_aggregate is None


def test_aggregate_invalid_window_raises():
    exts = [
        ext("faaster:hda:mode", "aggregate"),
        ext("faaster:hda:window", "30sec"),
    ]
    with pytest.raises(ValueError, match="Invalid faaster:hda:window"):
        extract_policy(exts)


def test_aggregate_invalid_function_raises():
    exts = [
        ext("faaster:hda:mode", "aggregate"),
        ext("faaster:hda:window", "15min"),
        ext("faaster:hda:function", "median"),
    ]
    with pytest.raises(ValueError, match="Invalid faaster:hda:function"):
        extract_policy(exts)


def test_aggregate_window_is_required():
    exts = [ext("faaster:hda:mode", "aggregate")]
    with pytest.raises(ValueError, match="faaster:hda:window is required"):
        extract_policy(exts)


def test_window_seconds_without_window():
    assert AggregationPolicy().window_seconds is None


# ------------------------------------------------------------------
# Levels e retenções
# ------------------------------------------------------------------

def test_levels_any_order_and_deduplicated():
    exts = [ext("faaster:hda:levels", "1hour, 10min,15min,10min")]
    assert extract_policy(exts).levels == ["1hour", "10min", "15min"]


def test_unknown_level_raises():
    exts = [ext("faaster:hda:levels", "1min,2min")]
    with pytest.raises(ValueError, match="Invalid faaster:hda:levels value: '2min'"):
        extract_policy(exts)


@pytest.mark.parametrize("value, normalized", [
    ("14 days", "14 days"),
    ("1 year", "1 year"),
    ("2 Weeks", "2 weeks"),
    ("6 month", "6 months"),
    ("12hours", "12 hours"),
    ("None", None),
])
def test_retention_formats(value, normalized):
    exts = [ext("faaster:hda:levels", "1min"), ext("faaster:hda:retention:1min", value)]
    assert extract_policy(exts).retention["1min"] == normalized


@pytest.mark.parametrize("value", ["forever", "30", "0 days", "1 decade", "-1 day"])
def test_invalid_retention_raises(value):
    exts = [ext("faaster:hda:retention:raw", value)]
    with pytest.raises(ValueError, match="Invalid faaster:hda:retention:raw"):
        extract_policy(exts)


def test_invalid_aggregate_retention_raises():
    exts = [
        ext("faaster:hda:mode", "aggregate"),
        ext("faaster:hda:window", "15min"),
        ext("faaster:hda:retention", "5 anos"),
    ]
    with pytest.raises(ValueError, match="Invalid faaster:hda:retention value"):
        extract_policy(exts)


def test_raw_retention_must_outlive_refresh_window():
    # o level 1day é recalculado sobre os últimos 4 dias de dados raw
    exts = [ext("faaster:hda:retention:raw", "3 days")]
    with pytest.raises(ValueError, match="Level '1day'"):
        extract_policy(exts)


def test_level_retention_must_outlive_its_refresh_window():
    exts = [ext("faaster:hda:levels", "1hour"), ext("faaster:hda:retention:1hour", "2 hours")]
    with pytest.raises(ValueError, match="faaster:hda:retention:1hour"):
        extract_policy(exts)


def test_short_raw_retention_allowed_for_short_levels():
    exts = [ext("faaster:hda:levels", "1min,15min"), ext("faaster:hda:retention:raw", "2 hours")]
    assert extract_policy(exts).retention["raw"] == "2 hours"


# ------------------------------------------------------------------
# AggregationPolicy defaults diretos
# ------------------------------------------------------------------

def test_aggregation_policy_default_mode():
    policy = AggregationPolicy()
    assert policy.mode == HDAMode.sample


def test_aggregation_policy_default_function():
    policy = AggregationPolicy()
    assert policy.function == HDAFunction.mean

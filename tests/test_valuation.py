import pandas as pd
import pytest

from lollie import synthetic_scenarios as S
from lollie.analysis.baseline import AnalysisSettings, analyze_campaign_window
from lollie.valuation import DEFAULT_RATE_USD, LABEL, NOT_CALCULATED, TOOLTIP, estimate_streaming_value, format_money


def test_default_rate_is_four_tenths_of_a_cent():
    assert DEFAULT_RATE_USD == 0.004
    assert LABEL == "Estimated Streaming Value Change"


def test_documented_example_expected_100k_actual_125k_is_plus_25k_streams_and_100_dollars():
    change = 125_000 - 100_000
    value = estimate_streaming_value(change)
    assert value.streams_change == 25_000
    assert value.value == pytest.approx(100.0)
    assert value.display == "+$100.00"
    assert value.calculated


def test_rate_is_editable():
    assert estimate_streaming_value(10_000, 0.006).value == pytest.approx(60.0)
    assert estimate_streaming_value(10_000, 0.0035).display == "+$35.00"


def test_estimate_can_be_switched_off_entirely():
    value = estimate_streaming_value(25_000, enabled=False)
    assert not value.enabled and not value.calculated and value.display == "Off"


def test_not_calculated_without_a_valid_rate_or_difference():
    for rate in (None, 0, -0.004, float("nan")):
        assert estimate_streaming_value(1000, rate).display == NOT_CALCULATED
    for change in (None, float("nan")):
        result = estimate_streaming_value(change)
        assert result.display == NOT_CALCULATED and "no valid observed" in result.reason.lower()


def test_rate_is_not_applied_when_the_streams_are_not_spotify():
    value = estimate_streaming_value(5000, applies=False, reason_if_not_applicable="Apple Music is selected.")
    assert value.display == NOT_CALCULATED and "Apple Music" in value.reason


def test_negative_change_is_a_negative_estimate_not_a_loss():
    value = estimate_streaming_value(-10_000)
    assert value.display == "-$40.00"
    assert "loss" not in value.display.lower()
    assert "not a verified loss" in TOOLTIP


def test_large_values_drop_the_cents():
    assert format_money(2_345_678.9) == "+$2,345,679"
    assert format_money(0) == "$0.00"


def test_tooltip_states_the_limits():
    for phrase in ("not WMG revenue", "royalty income", "profit", "advertising ROI", "no universal fixed per-stream royalty", "Spotify streams only"):
        assert phrase in TOOLTIP


def test_expected_streams_never_depend_on_the_value_per_stream():
    scenario = S.small_change_stable()
    before = analyze_campaign_window(scenario.series, scenario.campaign_start, scenario.campaign_end, AnalysisSettings())
    for rate in (0.0, 0.004, 0.5):
        estimate_streaming_value(before.observed_change, rate)
        again = analyze_campaign_window(scenario.series, scenario.campaign_start, scenario.campaign_end, AnalysisSettings())
        assert again.during_expected == before.during_expected
        pd.testing.assert_series_equal(again.series["expected"], before.series["expected"])
    import inspect

    assert "rate" not in inspect.signature(analyze_campaign_window).parameters

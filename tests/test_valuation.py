"""Estimated Streaming Value Change (Spotify-only, separate from baseline)."""

import pandas as pd
import pytest

from lollie.analysis.baseline import AnalysisSettings, analyze_campaign_window
from lollie.analysis.baseline import spotify_observed_change
from lollie.valuation import DEFAULT_RATE_USD, estimate_streaming_value, format_money


def test_value_is_observed_change_times_rate():
    result = estimate_streaming_value(25_000, DEFAULT_RATE_USD)
    assert result.calculated
    assert result.value == pytest.approx(100.0)
    assert result.display == format_money(100.0)


def test_zero_and_negative_changes():
    assert estimate_streaming_value(0, DEFAULT_RATE_USD).value == pytest.approx(0.0)
    negative = estimate_streaming_value(-10_000, DEFAULT_RATE_USD)
    assert negative.calculated
    assert negative.value == pytest.approx(-40.0)


def test_disabled_and_missing_change_explain_why():
    assert estimate_streaming_value(100, enabled=False).display == "Off"
    missing = estimate_streaming_value(None, applies=True)
    assert not missing.calculated
    assert "observed streaming change" in missing.display.lower()


def test_spotify_only_rows_when_view_is_all_dsps():
    rows = []
    for day in pd.date_range("2026-02-01", periods=40):
        rows.append({"date": day, "market_code": "US", "market": "United States", "streams": 1000, "dsp": "Spotify", "scope": "total", "track_key": "a", "source_name": ""})
        rows.append({"date": day, "market_code": "US", "market": "United States", "streams": 300, "dsp": "Apple Music", "scope": "total", "track_key": "a", "source_name": ""})
    matched = pd.DataFrame(rows)
    start, end = pd.Timestamp("2026-02-10"), pd.Timestamp("2026-02-20")
    settings = AnalysisSettings(baseline_days=14)
    change, reason = spotify_observed_change(matched, ["US"], start, end, settings)
    assert reason == ""
    assert change is not None

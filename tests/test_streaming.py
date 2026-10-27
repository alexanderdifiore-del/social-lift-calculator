from datetime import datetime

import pandas as pd
import pytest

from lollie.constants import (
    ARTIST_TIER_MULTIPLIER,
    DSP_MULTIPLIER,
    MARKET_MULTIPLIER,
    PLATFORM_MULTIPLIER,
    POST_TYPE_MULTIPLIER,
)
from lollie.streaming import (
    apply_social_lift,
    daily_rhythm,
    detect_granularity,
    estimate_baseline,
    impact_window_mask,
    simulate_baseline,
    summarize_impact,
)

POST = datetime(2026, 10, 27, 18, 0, 0)


def _default_demo_frame():
    frame = simulate_baseline(
        POST,
        7,
        tier_multiplier=ARTIST_TIER_MULTIPLIER["Emerging"],
        market_multiplier=MARKET_MULTIPLIER["US"],
        dsp_multiplier=DSP_MULTIPLIER["All DSPs"],
    )
    return apply_social_lift(
        frame,
        POST,
        24,
        campaign_intensity=6,
        platform_multiplier=PLATFORM_MULTIPLIER["TikTok"],
        post_type_multiplier=POST_TYPE_MULTIPLIER["Organic artist post"],
    )


def test_daily_rhythm_peak_evening():
    assert daily_rhythm(18) == 1.45
    assert daily_rhythm(3) == 0.55


def test_matches_original_lollie_default_numbers():
    """The original app's default view: 65,367 expected / 148,717 actual / 83,350 lift."""
    frame = _default_demo_frame()
    mask = impact_window_mask(frame["timestamp"], POST, 24)
    summary = summarize_impact(frame, mask)
    assert round(summary.expected) == 65_367
    assert round(summary.actual) == 148_717
    assert round(summary.lift) == 83_350
    assert round(summary.baseline_rate) == 2_740
    assert summary.lift_percent == pytest.approx(127.5, abs=0.1)


def test_simulation_is_deterministic():
    a = _default_demo_frame()
    b = _default_demo_frame()
    pd.testing.assert_frame_equal(a, b)


def test_lift_only_changes_rows_inside_window():
    frame = _default_demo_frame()
    outside = ~impact_window_mask(frame["timestamp"], POST, 24)
    assert (frame.loc[outside, "actual_streams"] == frame.loc[outside, "expected_baseline_streams"]).all()


def test_detect_granularity_hourly_vs_daily():
    hourly = pd.Series(pd.date_range("2026-10-01", periods=48, freq="h"))
    daily = pd.Series(pd.date_range("2026-10-01", periods=10, freq="D"))
    assert detect_granularity(hourly) == "intraday"
    assert detect_granularity(daily) == "daily"


def test_daily_window_uses_whole_days_from_post_date():
    days = pd.Series(pd.date_range("2026-10-20", periods=14, freq="D"))
    mask = impact_window_mask(days, POST, 48, granularity="daily")
    assert days[mask].dt.day.tolist() == [27, 28]


def test_estimate_baseline_intraday_uses_hour_of_day_history():
    ts = pd.date_range("2026-10-20", periods=24 * 7, freq="h")
    frame = pd.DataFrame({"timestamp": ts, "actual_streams": [100 + t.hour for t in ts]})
    baseline = estimate_baseline(frame, datetime(2026, 10, 24, 12), 24)
    assert baseline.iloc[5] == pytest.approx(105)


def test_estimate_baseline_daily_excludes_the_event_window():
    ts = pd.date_range("2026-10-01", periods=28, freq="D")
    actual = [1000] * 28
    actual[26] = 5000
    frame = pd.DataFrame({"timestamp": ts, "actual_streams": actual})
    baseline = estimate_baseline(frame, datetime(2026, 10, 27, 12), 24, granularity="daily")
    assert (baseline == 1000).all()
    summary = summarize_impact(
        frame.assign(expected_baseline_streams=baseline),
        impact_window_mask(frame["timestamp"], datetime(2026, 10, 27, 12), 24, "daily"),
    )
    assert summary.lift == 4000


def test_zero_expected_gives_no_percent():
    frame = pd.DataFrame(
        {"timestamp": pd.date_range("2026-10-01", periods=2, freq="D"),
         "expected_baseline_streams": [0, 0], "actual_streams": [5, 5]}
    )
    summary = summarize_impact(frame, pd.Series([True, True]))
    assert summary.lift_percent is None

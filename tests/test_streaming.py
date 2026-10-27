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


def _hourly_upload(days=10):
    import numpy as np

    ts = pd.date_range("2026-10-01", periods=days * 24, freq="h")
    values = 1000 + 200 * np.sin(ts.hour / 24 * 2 * np.pi)
    return pd.DataFrame({"When": ts.astype(str), "Plays": values.round()})


def test_prepare_hourly_upload_estimates_baseline_from_history():
    from lollie.streaming import prepare_streaming_frame

    raw = _hourly_upload()
    raw.loc[(pd.to_datetime(raw["When"]) >= "2026-10-08 18:00") & (pd.to_datetime(raw["When"]) < "2026-10-09 18:00"), "Plays"] *= 2
    prep = prepare_streaming_frame(
        raw, "When", "Plays", None, post_timestamp=datetime(2026, 10, 8, 18), impact_window_hours=24
    )
    assert prep.error is None and prep.granularity == "intraday" and prep.baseline_estimated
    mask = impact_window_mask(prep.frame["timestamp"], datetime(2026, 10, 8, 18), 24, "intraday")
    result = summarize_impact(prep.frame, mask)
    assert result.lift > 0 and 90 < result.lift_percent < 110


def test_prepare_daily_upload_stays_daily_and_is_never_made_hourly():
    from lollie.streaming import prepare_streaming_frame

    days = pd.date_range("2026-09-01", periods=40)
    raw = pd.DataFrame({"Date": days.astype(str), "Streams": [50_000] * 40})
    raw.loc[raw["Date"] == "2026-10-05", "Streams"] = 80_000
    prep = prepare_streaming_frame(
        raw, "Date", "Streams", None, post_timestamp=datetime(2026, 10, 5, 12), impact_window_hours=24
    )
    assert prep.granularity == "daily"
    assert len(prep.frame) == 40
    mask = impact_window_mask(prep.frame["timestamp"], datetime(2026, 10, 5, 12), 24, "daily")
    assert mask.sum() == 1
    assert summarize_impact(prep.frame, mask).lift == 30_000


def test_prepare_upload_rejects_bad_mapping_and_filters_markets():
    from lollie.streaming import prepare_streaming_frame

    raw = pd.DataFrame(
        {
            "Date": ["2026-10-01", "2026-10-01", "2026-10-02", "2026-10-02"],
            "Streams": [100, 50, 120, 60],
            "Country": ["US", "UK", "US", "UK"],
        }
    )
    bad = prepare_streaming_frame(raw, "Date", "Date", None, post_timestamp=datetime(2026, 10, 2), impact_window_hours=24)
    assert bad.error
    us = prepare_streaming_frame(
        raw, "Date", "Streams", None, post_timestamp=datetime(2026, 10, 2), impact_window_hours=24,
        market_column="Country", market="US",
    )
    assert us.frame["actual_streams"].tolist() == [100, 120]
    both = prepare_streaming_frame(
        raw, "Date", "Streams", None, post_timestamp=datetime(2026, 10, 2), impact_window_hours=24,
        market_column="Country", market="All markets",
    )
    assert both.frame["actual_streams"].tolist() == [150, 180]
    assert any("added together" in note for note in both.notes)


def test_manual_summary_without_expected_has_no_percent():
    from lollie.streaming import manual_summary

    assert manual_summary(0, 100).lift_percent is None
    assert manual_summary(100, 150).lift_percent == 50.0

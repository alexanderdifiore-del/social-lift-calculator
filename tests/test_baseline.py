import numpy as np
import pandas as pd
import pytest

from lollie.analysis.baseline import (
    METHOD_NONE,
    METHOD_OVERALL,
    METHOD_WEEKDAY,
    AnalysisSettings,
    aggregate_daily,
    analyze_campaign_window,
    baseline_window,
    label_change,
)

START, END = pd.Timestamp("2026-02-10"), pd.Timestamp("2026-02-20")


def series(level=1000.0, days=70, first="2026-01-01"):
    idx = pd.date_range(first, periods=days)
    return pd.Series(level, index=idx, dtype=float)


def test_baseline_window_ends_the_day_before_launch_and_can_skip_days():
    assert baseline_window(START, AnalysisSettings(baseline_days=28)) == (pd.Timestamp("2026-01-13"), pd.Timestamp("2026-02-09"))
    assert baseline_window(START, AnalysisSettings(baseline_days=7, gap_days=2)) == (pd.Timestamp("2026-02-01"), pd.Timestamp("2026-02-07"))


def test_flat_streams_show_no_change():
    result = analyze_campaign_window(series(), START, END)
    assert result.method == METHOD_WEEKDAY
    assert result.observed_change == pytest.approx(0)
    assert result.pct_change == pytest.approx(0)
    assert result.baseline.average == pytest.approx(1000)


def test_known_increase_is_measured_exactly():
    s = series()
    s.loc[START:END] *= 1.25
    result = analyze_campaign_window(s, START, END)
    assert result.pct_change == pytest.approx(0.25)
    assert result.observed_change == pytest.approx(250 * 11)
    assert result.during_actual == pytest.approx(1250 * 11)
    assert result.during_expected == pytest.approx(1000 * 11)


def test_weekday_pattern_is_not_mistaken_for_a_lift():
    idx = pd.date_range("2026-01-01", periods=70)
    s = pd.Series(np.where(idx.day_of_week >= 5, 1500.0, 1000.0), index=idx)
    result = analyze_campaign_window(s, START, END)
    assert result.method == METHOD_WEEKDAY
    assert result.pct_change == pytest.approx(0, abs=1e-9)


def test_short_baseline_falls_back_to_overall_median():
    s = series(first="2026-01-30", days=40)
    result = analyze_campaign_window(s, START, END, AnalysisSettings(baseline_days=28, min_baseline_days=7))
    assert result.method == METHOD_OVERALL
    assert result.expected_value == pytest.approx(1000)


def test_too_little_baseline_data_gives_no_expected_line_and_says_why():
    s = series(first="2026-02-07", days=30)
    result = analyze_campaign_window(s, START, END)
    assert result.method == METHOD_NONE
    assert result.pct_change is None and result.expected_value is None
    assert result.series["expected"].isna().all()
    assert any("baseline" in flag.lower() for flag in result.flags)


def test_missing_days_are_left_out_of_both_actual_and_expected():
    s = series()
    s.loc[START:END] *= 1.2
    s = s.drop(pd.date_range("2026-02-12", "2026-02-14"))
    result = analyze_campaign_window(s, START, END)
    assert result.during.days_with_data == 8
    assert result.pct_change == pytest.approx(0.2)  # a data gap does not look like a drop
    assert result.during.coverage == pytest.approx(8 / 11)
    assert any("8 of 11" in flag for flag in result.flags)


def test_after_campaign_window_is_compared_with_the_same_baseline():
    s = series()
    post = pd.date_range(END + pd.Timedelta(days=1), periods=14)
    s.loc[post] *= 1.1
    result = analyze_campaign_window(s, START, END, AnalysisSettings(post_days=14))
    assert result.post_pct_change == pytest.approx(0.10)
    assert result.post.days_in_window == 14


def test_no_data_after_campaign_is_flagged():
    s = series(days=51)  # ends on the campaign end date
    result = analyze_campaign_window(s, START, END)
    assert result.post.days_with_data == 0
    assert any("after the campaign" in flag for flag in result.flags)


def test_rising_baseline_trend_is_flagged():
    idx = pd.date_range("2026-01-01", periods=70)
    s = pd.Series(np.linspace(1000, 2000, 70), index=idx)
    result = analyze_campaign_window(s, START, END)
    assert any("already rising" in flag for flag in result.flags)


def test_chart_series_labels_windows():
    result = analyze_campaign_window(series(), START, END, AnalysisSettings(post_days=3))
    windows = result.series.set_index("date")["window"]
    assert windows[pd.Timestamp("2026-02-09")] == "Before"
    assert windows[START] == "During" and windows[END] == "During"
    assert windows[pd.Timestamp("2026-02-21")] == "After"
    assert result.series["date"].max() == pd.Timestamp("2026-02-23")


def test_reversed_dates_are_swapped_rather_than_failing():
    result = analyze_campaign_window(series(), END, START)
    assert result.start == START and result.end == END


def test_combined_markets_ignore_days_when_a_country_did_not_report():
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-01", "2026-01-02"]),
            "market_code": ["US", "DE", "US"],
            "market": ["United States", "Germany", "United States"],
            "streams": [100, 50, 100],
        }
    )
    combined, notes = aggregate_daily(daily, ["US", "DE"])
    assert combined.index.tolist() == [pd.Timestamp("2026-01-01")]
    assert combined.iloc[0] == 150
    assert notes and "missing" in notes[0]
    single, notes = aggregate_daily(daily, ["US"])
    assert single.tolist() == [100, 100] and not notes


@pytest.mark.parametrize(
    "value,label",
    [(0.25, "Higher than baseline"), (-0.2, "Lower than baseline"), (0.02, "Close to baseline"), (None, "Not available")],
)
def test_change_labels_use_neutral_wording(value, label):
    assert label_change(value) == label

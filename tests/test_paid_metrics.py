import numpy as np
import pandas as pd
import pytest

from lollie.paid.metrics import (
    STATUS_AHEAD,
    STATUS_AT_RISK,
    STATUS_ON_TRACK,
    STATUS_UNAVAILABLE,
    Thresholds,
    aggregate_kpis,
    budget_pacing,
    campaign_market_table,
    classify_status,
    cost_per_result,
    cpc,
    cpm,
    ctr,
    forecast_attainment,
    overall_pacing,
    pacing_label,
    results_by_type,
)
from lollie.paid.schema import CANONICAL_FIELDS


def make_frame(rows):
    frame = pd.DataFrame(rows)
    for col in CANONICAL_FIELDS:
        if col not in frame:
            frame[col] = np.nan if col in {"impressions", "views", "engagements", "clicks", "spend", "results", "budget", "results_goal"} else None
    for col in ("date", "start_date", "end_date"):
        frame[col] = pd.to_datetime(frame[col])
    frame["currency"] = frame["currency"].fillna("USD")
    frame["market"] = frame["market"].fillna("US")
    return frame


def test_basic_delivery_metrics_use_gross_spend():
    assert cpm(500, 100_000) == pytest.approx(5.0)
    assert cpc(500, 250) == pytest.approx(2.0)
    assert ctr(250, 100_000) == pytest.approx(0.0025)
    assert cost_per_result(500, 125) == pytest.approx(4.0)


def test_metrics_return_none_instead_of_dividing_by_zero():
    assert cpm(100, 0) is None
    assert cpc(100, None) is None
    assert ctr(5, 0) is None
    assert cost_per_result(100, np.nan) is None


def test_aggregate_kpis_totals_and_budget_counted_once_per_campaign():
    frame = make_frame(
        [
            {"date": "2026-10-01", "platform": "Meta Ads", "campaign_name": "A", "impressions": 1000, "clicks": 10, "spend": 50, "budget": 1000},
            {"date": "2026-10-02", "platform": "Meta Ads", "campaign_name": "A", "impressions": 3000, "clicks": 30, "spend": 150, "budget": 1000},
            {"date": "2026-10-01", "platform": "TikTok Ads", "campaign_name": "B", "impressions": 6000, "clicks": 60, "spend": 300, "budget": 2000},
        ]
    )
    kpis = aggregate_kpis(frame)
    assert kpis["spend"] == 500
    assert kpis["impressions"] == 10_000
    assert kpis["budget"] == 3000
    assert kpis["cpm"] == pytest.approx(50.0)
    assert kpis["cpc"] == pytest.approx(5.0)
    assert kpis["ctr"] == pytest.approx(0.01)
    assert kpis["campaigns"] == 2


def test_metrics_never_reported_stay_none_not_zero():
    frame = make_frame([{"date": "2026-10-01", "platform": "Meta Ads", "campaign_name": "A", "spend": 10}])
    kpis = aggregate_kpis(frame)
    assert kpis["impressions"] is None and kpis["views"] is None and kpis["cpm"] is None


def test_results_are_never_added_across_result_types():
    frame = make_frame(
        [
            {"date": "2026-10-01", "platform": "Meta Ads", "campaign_name": "A", "impressions": 1000, "spend": 100, "results": 50, "result_family": "landing_page_views"},
            {"date": "2026-10-01", "platform": "TikTok Ads", "campaign_name": "B", "impressions": 1000, "spend": 100, "results": 4000, "result_family": "video_views"},
        ]
    )
    table = results_by_type(frame)
    assert set(table["family"]) == {"landing_page_views", "video_views"}
    lpv = table.set_index("family").loc["landing_page_views"]
    assert lpv["Results"] == 50 and lpv["Cost per result"] == pytest.approx(2.0)


@pytest.mark.parametrize(
    "spend,budget,elapsed,total,expected",
    [(500, 1000, 5, 10, 1.0), (300, 1000, 5, 10, 0.6), (700, 1000, 5, 10, 1.4), (900, 1000, 20, 10, 0.9)],
)
def test_budget_pacing_vs_even_spend_plan(spend, budget, elapsed, total, expected):
    assert budget_pacing(spend, budget, elapsed, total) == pytest.approx(expected)


def test_budget_pacing_unavailable_without_budget_or_dates():
    assert budget_pacing(100, None, 5, 10) is None
    assert budget_pacing(100, 1000, None, None) is None
    assert pacing_label(None) == "Pacing unavailable"
    assert pacing_label(1.0) == "On pace"
    assert pacing_label(1.3) == "Ahead of plan"
    assert pacing_label(0.5) == "Behind plan"


def test_forecast_projects_run_rate_over_the_full_flight():
    assert forecast_attainment(400, 1000, 4, 10, finished=False) == pytest.approx(1.0)
    assert forecast_attainment(200, 1000, 4, 10, finished=False) == pytest.approx(0.5)


def test_forecast_uses_actuals_once_flight_has_ended():
    assert forecast_attainment(800, 1000, 10, 10, finished=True) == pytest.approx(0.8)


def test_forecast_unavailable_cases():
    assert forecast_attainment(100, None, 4, 10, False) is None
    assert forecast_attainment(100, 0, 4, 10, False) is None
    assert forecast_attainment(None, 1000, 4, 10, False) is None
    assert forecast_attainment(100, 1000, 4, None, False) is None


def test_status_indicators_and_configurable_thresholds():
    assert classify_status(1.25) == STATUS_AHEAD
    assert classify_status(1.00) == STATUS_ON_TRACK
    assert classify_status(0.89) == STATUS_AT_RISK
    assert classify_status(None) == STATUS_UNAVAILABLE
    strict = Thresholds(ahead=1.5, on_track=1.0)
    assert classify_status(1.25, strict) == STATUS_ON_TRACK
    assert classify_status(0.95, strict) == STATUS_AT_RISK


def _two_market_frame():
    days = pd.date_range("2026-10-01", periods=5)
    rows = []
    for d in days:
        rows.append({"date": d, "platform": "TikTok Ads", "campaign_name": "Sound Push", "market": "US", "objective": "Video views",
                     "impressions": 10_000, "spend": 100, "results": 5000, "result_family": "video_views", "budget": 2000,
                     "results_goal": 40_000, "start_date": "2026-10-01", "end_date": "2026-10-10"})
        rows.append({"date": d, "platform": "TikTok Ads", "campaign_name": "Sound Push", "market": "UK", "objective": "Video views",
                     "impressions": 10_000, "spend": 100, "results": 1000, "result_family": "video_views", "budget": 2000,
                     "results_goal": 40_000, "start_date": "2026-10-01", "end_date": "2026-10-10"})
    return make_frame(rows)


def test_market_table_status_per_market_and_timing():
    table = campaign_market_table(_two_market_frame(), pd.Timestamp("2026-10-05"))
    by_market = table.set_index("Market")
    # US: 25,000 results in 5 of 10 days projects to 50,000 vs a 40,000 goal (125%).
    assert by_market.loc["US", "Goal status"] == STATUS_AHEAD
    assert by_market.loc["US", "Forecast attainment"] == pytest.approx(1.25)
    # UK: 5,000 results in 5 of 10 days projects to 10,000 vs 40,000 (25%).
    assert by_market.loc["UK", "Forecast attainment"] == pytest.approx(0.25)
    assert by_market.loc["UK", "Goal status"] == STATUS_AT_RISK
    assert by_market.loc["US", "Days remaining"] == 5
    assert by_market.loc["US", "Campaign status"] == "Active"
    assert by_market.loc["US", "Spend"] == 500
    assert by_market.loc["US", "CPM"] == pytest.approx(10.0)
    assert by_market.loc["US", "Cost per result"] == pytest.approx(0.02)
    # $500 spent of a $2,000 budget with half the flight elapsed -> 50% of planned spend.
    assert by_market.loc["US", "Pacing"] == pytest.approx(0.5)


def test_market_table_marks_ended_and_unavailable():
    frame = _two_market_frame()
    frame["results_goal"] = np.nan
    table = campaign_market_table(frame, pd.Timestamp("2026-10-20"))
    assert (table["Campaign status"] == "Ended").all()
    assert (table["Goal status"] == STATUS_UNAVAILABLE).all()


def test_overall_pacing_is_spend_weighted_and_ignores_unbudgeted_campaigns():
    frame = _two_market_frame()
    pacing = overall_pacing(frame, pd.Timestamp("2026-10-05"))
    assert pacing == pytest.approx(0.5)
    assert pacing_label(pacing) == "Behind plan"
    frame["budget"] = np.nan
    assert overall_pacing(frame, pd.Timestamp("2026-10-05")) is None

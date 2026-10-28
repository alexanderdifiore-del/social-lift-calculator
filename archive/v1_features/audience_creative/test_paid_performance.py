import numpy as np
import pandas as pd
import pytest

from lollie.paid.metrics import aggregate_kpis, campaign_market_table
from lollie.paid.performance import (
    best_cost_effective,
    best_engaging,
    best_result_rate,
    rank_dimension,
)
from lollie.paid.report import build_recap
from lollie.paid.timeseries import daily_series, flights, overlap_report
from tests.test_paid_metrics import make_frame


def _frame():
    rows = []
    specs = [
        # platform, audience, creative, family, impressions, spend, results, engagements
        ("Meta Ads", "Lookalike", "Reel A", "landing_page_views", 100_000, 1000, 500, 4000),
        ("Meta Ads", "Interest", "Reel B", "landing_page_views", 100_000, 1000, 800, 6000),
        ("TikTok Ads", "Broad", "Studio 15s", "video_views", 100_000, 400, 40_000, 9000),
        ("TikTok Ads", "Creators", "UGC", "video_views", 100_000, 400, 30_000, 12000),
        ("Meta Ads", "Tiny audience", "Reel C", "landing_page_views", 200, 1, 1, 50),
    ]
    for platform, audience, creative, family, impr, spend, results, eng in specs:
        rows.append({"date": "2026-10-02", "platform": platform, "campaign_name": "C", "audience": audience, "creative": creative,
                     "result_family": family, "impressions": impr, "spend": spend, "results": results, "engagements": eng})
    return make_frame(rows)


def test_cost_per_result_is_only_compared_within_one_result_type():
    ranking = rank_dimension(_frame(), "audience")
    best_lpv = best_cost_effective(ranking, "landing_page_views")
    best_video = best_cost_effective(ranking, "video_views")
    assert best_lpv["Audience"] == "Interest"  # $1.25 vs $2.00 per landing page view
    assert best_video["Audience"] == "Broad"  # $0.01 vs $0.0133 per video view
    assert best_cost_effective(ranking) is None  # mixed result types -> no single winner


def test_engagement_rate_is_only_compared_within_a_platform():
    ranking = rank_dimension(_frame(), "audience")
    assert best_engaging(ranking) is None  # two platforms, definitions differ
    assert best_engaging(ranking, "Meta Ads")["Audience"] == "Interest"
    assert best_engaging(ranking, "TikTok Ads")["Audience"] == "Creators"


def test_noise_floor_excludes_tiny_audiences():
    ranking = rank_dimension(_frame(), "audience", min_impressions=1000)
    assert "Tiny audience" not in set(ranking["Audience"])
    loose = rank_dimension(_frame(), "audience", min_impressions=0)
    assert "Tiny audience" in set(loose["Audience"])


def test_best_creative_and_result_rate():
    ranking = rank_dimension(_frame(), "creative")
    assert best_cost_effective(ranking, "video_views")["Creative"] == "Studio 15s"
    assert best_result_rate(ranking, "landing_page_views")["Creative"] == "Reel B"
    with pytest.raises(ValueError):
        rank_dimension(_frame(), "market")


def test_empty_when_no_audience_or_creative_columns():
    frame = _frame().assign(audience=None)
    assert rank_dimension(frame, "audience").empty
    assert best_cost_effective(pd.DataFrame()) is None


def test_daily_series_uses_only_real_dates_and_sums_by_day():
    frame = make_frame(
        [
            {"date": "2026-10-01", "platform": "A", "campaign_name": "x", "spend": 10, "impressions": 100},
            {"date": "2026-10-01", "platform": "B", "campaign_name": "y", "spend": 5, "impressions": 50},
            {"date": "2026-10-03", "platform": "A", "campaign_name": "x", "spend": 7, "impressions": 70},
            {"date": None, "platform": "A", "campaign_name": "x", "spend": 99, "impressions": 999},
        ]
    )
    daily = daily_series(frame)
    assert daily["date"].dt.day.tolist() == [1, 3]  # no fabricated 2026-10-02 row
    assert daily["spend"].tolist() == [15, 7]


def test_flights_use_explicit_dates_else_first_and_last_day():
    frame = make_frame(
        [
            {"date": "2026-10-03", "platform": "A", "campaign_name": "x", "spend": 1},
            {"date": "2026-10-06", "platform": "A", "campaign_name": "x", "spend": 1},
            {"date": "2026-10-01", "platform": "B", "campaign_name": "y", "spend": 1, "start_date": "2026-09-30", "end_date": "2026-10-09"},
        ]
    )
    result = flights(frame).set_index("campaign")
    assert result.loc["x", "start"] == pd.Timestamp("2026-10-03")
    assert result.loc["x", "end"] == pd.Timestamp("2026-10-07")
    assert result.loc["y", "start"] == pd.Timestamp("2026-09-30")


def test_overlap_report_flags_missing_and_mismatched_data():
    daily = pd.DataFrame({"date": pd.to_datetime(["2026-10-05", "2026-10-06"])})
    stream = pd.Series(pd.to_datetime(["2026-10-05", "2026-10-07"]))
    notes = " ".join(overlap_report(daily, stream))
    assert "missing for 1 day" in notes
    far = pd.Series(pd.to_datetime(["2026-01-01", "2026-01-02"]))
    assert "do not overlap" in " ".join(overlap_report(daily, far))
    assert "No streaming data" in " ".join(overlap_report(daily, None))
    assert "no dated rows" in " ".join(overlap_report(pd.DataFrame(), stream))


def test_recap_is_factual_and_flags_unavailable_data():
    frame = _frame()
    kpis = aggregate_kpis(frame)
    table = campaign_market_table(frame, pd.Timestamp("2026-10-05"))
    ranking = rank_dimension(frame, "audience")
    text = build_recap(
        artist="Artist",
        release="Song",
        campaign_id="C-1",
        kpis=kpis,
        currency="USD",
        platforms=["Meta Ads", "TikTok Ads"],
        pacing=None,
        market_table=table,
        as_of=pd.Timestamp("2026-10-05"),
        best_audience_cost=best_cost_effective(ranking, "landing_page_views"),
        best_audience_engaging=best_engaging(ranking, "Meta Ads"),
        best_creative_cost=None,
        streaming={"window": "24h", "actual": 148_717, "expected": 65_367, "lift_percent": 127.5},
    )
    assert "Artist - Song" in text
    assert "Spend: $2,801" in text
    assert "Budget pacing: unavailable" in text
    assert "Forecast unavailable" in text
    assert "Most cost-effective audience: Interest" in text
    assert "Best-performing creative: not enough comparable data" in text
    assert "+127.5%" in text
    assert "not proof" in text


def test_recap_without_streaming_says_so_instead_of_inventing_results():
    kpis = aggregate_kpis(_frame())
    text = build_recap(
        artist="A", release="S", campaign_id="C", kpis=kpis, currency="USD", platforms=[],
        pacing=0.8, market_table=pd.DataFrame(), as_of=pd.Timestamp("2026-10-05"),
    )
    assert "No streaming data loaded" in text
    assert "behind plan" in text
    assert "No market-level data" in text

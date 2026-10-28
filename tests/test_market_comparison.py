import numpy as np
import pandas as pd
import pytest

from lollie.analysis.baseline import AnalysisSettings
from lollie.analysis.campaigns import campaign_comparison, campaign_dates, overlap_notes, repeated_pattern_note
from lollie.analysis.markets import LOW, PAID, market_comparison, market_rank_note
from lollie.analysis.relationships import NONE, POSITIVE, lag_relationship, rank_relationship
from lollie.geo import normalize_market
from lollie.paid.ingest import normalize_paid_frame
from lollie.paid.schema import PLATFORM_WAVO

START, END = pd.Timestamp("2026-03-01"), pd.Timestamp("2026-03-14")
SETTINGS = AnalysisSettings(baseline_days=28, post_days=7)


def paid_rows(campaign="C1", markets=(("US", 1000.0),), start=START, end=END):
    rows = []
    for market, budget in markets:
        for day in pd.date_range(start, end):
            rows.append({
                "campaign_name": campaign, "platform": "Meta Ads", "market": market,
                "market_code": normalize_market(market)[0], "date": day, "start_date": start, "end_date": end,
                "spend": budget / ((end - start).days + 1), "impressions": 1000.0, "clicks": 10.0, "landing_page_views": 5.0,
                "promoted_item": None, "currency": "USD",
            })
    return pd.DataFrame(rows)


def streaming(markets, lift=None, first="2026-01-15", last="2026-04-10"):
    lift = lift or {}
    rows = []
    for code, base in markets.items():
        for day in pd.date_range(first, last):
            value = base * (1 + (lift.get(code, 0.0) if START <= day <= END else 0.0))
            rows.append({"date": day, "market_code": code, "market": code, "streams": value})
    return pd.DataFrame(rows)


def test_paid_and_streaming_countries_line_up_across_naming_styles():
    paid = paid_rows(markets=(("United States", 500.0), ("Deutschland", 500.0)))
    table, _, _ = market_comparison(paid, streaming({"US": 1000, "DE": 800}), START, END, SETTINGS)
    assert set(table["market_code"]) == {"US", "DE"}
    assert table["Change vs baseline"].notna().all()


def test_each_country_gets_its_own_observed_change():
    paid = paid_rows(markets=(("US", 600.0), ("GB", 400.0)))
    table, analyses, _ = market_comparison(paid, streaming({"US": 1000, "GB": 500}, lift={"US": 0.3, "GB": 0.0}), START, END, SETTINGS)
    by = table.set_index("market_code")
    assert by.loc["US", "Change vs baseline"] == pytest.approx(0.3)
    assert by.loc["GB", "Change vs baseline"] == pytest.approx(0.0)
    assert by.loc["US", "Observed change (streams)"] == pytest.approx(300 * 14)
    assert analyses["US"].method


def test_countries_without_paid_activity_are_reference_only_never_a_control():
    paid = paid_rows(markets=(("US", 1000.0),))
    table, _, relations = market_comparison(paid, streaming({"US": 1000, "FR": 500}, lift={"US": 0.3}), START, END, SETTINGS)
    france = table.set_index("market_code").loc["FR"]
    assert france["Paid activity"] == LOW
    assert france["Spend and streaming pattern"] == "Not assessed"
    assert "FR" not in relations
    assert any("No paid activity" in note for note in [france["Notes"]])


def test_paid_country_without_streaming_data_is_listed_with_a_note():
    paid = paid_rows(markets=(("US", 500.0), ("MX", 500.0)))
    table, _, _ = market_comparison(paid, streaming({"US": 1000}), START, END, SETTINGS)
    mexico = table.set_index("market_code").loc["MX"]
    assert pd.isna(mexico["Change vs baseline"]) and mexico["Reading"] == "No streaming data"
    assert "No streaming data" in mexico["Notes"]


def test_daily_spend_that_tracks_streaming_is_called_a_potential_relationship_only():
    days = pd.date_range(START, END)
    spend = pd.Series(np.linspace(100, 1000, len(days)), index=days)
    idx = pd.date_range("2026-01-15", "2026-04-10")
    actual = pd.Series(1000.0, index=idx)
    actual.loc[days] = 1000 + spend.values
    expected = pd.Series(1000.0, index=idx)
    result = lag_relationship(spend, actual, expected)
    assert result.label == POSITIVE
    assert result.best_lag == 0 and result.correlation > 0.99


def test_relationship_needs_enough_days_and_varying_spend():
    days = pd.date_range(START, START + pd.Timedelta(days=4))
    result = lag_relationship(pd.Series(1.0, index=days), pd.Series(1.0, index=days), pd.Series(1.0, index=days))
    assert result.label == "Not enough data"
    flat = pd.date_range(START, END)
    result = lag_relationship(pd.Series(100.0, index=flat), pd.Series(np.arange(14.0), index=flat), pd.Series(0.0, index=flat))
    assert result.label == "Not enough data"


def test_spend_that_moves_with_streams_but_no_overall_lift_is_not_called_positive():
    days = pd.date_range(START, END)
    rng = np.random.default_rng(1)
    spend_values = rng.uniform(50, 150, len(days))
    paid = paid_rows(markets=(("US", 1000.0),))
    paid["spend"] = spend_values
    stream = streaming({"US": 1000})
    stream.loc[stream["date"].isin(days), "streams"] = 1000 + (spend_values - spend_values.mean()) * 5
    table, _, relations = market_comparison(paid, stream, START, END, SETTINGS)
    assert relations["US"].label in (NONE, "Not enough data")


def test_rank_relationship_requires_four_countries():
    assert rank_relationship(pd.Series([1, 2, 3]), pd.Series([0.1, 0.2, 0.3]))[0] is None
    rho, n = rank_relationship(pd.Series([1, 2, 3, 4]), pd.Series([0.1, 0.2, 0.3, 0.4]))
    assert rho == pytest.approx(1.0) and n == 4


def test_market_rank_note_is_a_rough_guide():
    table = pd.DataFrame({"Paid activity": [PAID] * 5, "Ad spend": [1, 2, 3, 4, 5], "Change vs baseline": [0.0, 0.05, 0.1, 0.2, 0.3]})
    note = market_rank_note(table)
    assert "larger change" in note and "rough guide" in note


def test_campaign_dates_prefer_the_report_then_fall_back_to_reporting_days():
    rows = paid_rows()
    assert campaign_dates(rows).inferred is False
    rows["start_date"] = pd.NaT
    rows["end_date"] = pd.NaT
    inferred = campaign_dates(rows)
    assert inferred.inferred and inferred.start == START and inferred.end == END and inferred.note
    assert campaign_dates(rows.iloc[0:0]).known is False


def test_paid_report_dates_in_different_formats_align_with_streaming_dates():
    raw = pd.DataFrame(
        {
            "Campaign Name": ["C1"] * 2, "Reporting Date": ["03/01/2026", "03/02/2026"], "Country": ["USA", "United States"],
            "Spend": [10, 20], "Campaign Start": ["2026-03-01"] * 2, "Campaign End": ["Mar 14, 2026"] * 2,
        }
    )
    from lollie.paid.ingest import suggest_mapping

    result = normalize_paid_frame(raw, suggest_mapping(list(raw.columns)), PLATFORM_WAVO)
    assert result.frame["market_code"].tolist() == ["US", "US"]
    dates = campaign_dates(result.frame)
    assert (dates.start, dates.end) == (START, END)


def test_overlapping_campaign_and_polluted_baseline_are_reported():
    main = paid_rows("Main")
    overlap = paid_rows("Overlap", start=pd.Timestamp("2026-03-10"), end=pd.Timestamp("2026-03-20"))
    earlier = paid_rows("Earlier", start=pd.Timestamp("2026-02-01"), end=pd.Timestamp("2026-02-10"))
    notes = overlap_notes(pd.concat([main, overlap, earlier]), "Main", START, END, SETTINGS)
    assert any("Overlapping campaign: 'Overlap'" in n for n in notes)
    assert any("Baseline contains another campaign: 'Earlier'" in n for n in notes)
    assert overlap_notes(main, "Main", START, END, SETTINGS) == []


def test_campaigns_in_other_countries_do_not_count_as_overlap():
    main = paid_rows("Main", markets=(("US", 100.0),))
    other = paid_rows("Other", markets=(("BR", 100.0),))
    assert overlap_notes(pd.concat([main, other]), "Main", START, END, SETTINGS, ["US"]) == []


def test_campaign_comparison_uses_each_campaigns_own_baseline_and_countries():
    first = paid_rows("First", markets=(("US", 500.0),))
    later = paid_rows("Later", markets=(("US", 500.0),), start=pd.Timestamp("2026-04-01"), end=pd.Timestamp("2026-04-07"))
    stream = streaming({"US": 1000}, lift={"US": 0.4}, last="2026-04-20")
    table, analyses = campaign_comparison(pd.concat([first, later]), stream, SETTINGS)
    assert table["Campaign"].tolist() == ["First", "Later"]
    assert table.loc[0, "Change vs baseline"] == pytest.approx(0.4)
    assert set(analyses) == {"First", "Later"}
    assert repeated_pattern_note(table) is not None


def test_repeated_pattern_note_needs_two_campaigns():
    assert repeated_pattern_note(pd.DataFrame({"Change vs baseline": [0.3]})) is None
    note = repeated_pattern_note(pd.DataFrame({"Change vs baseline": [0.3, 0.2]}))
    assert "does not show the ads caused it" in note

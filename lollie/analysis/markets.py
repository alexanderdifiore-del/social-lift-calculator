"""Country-by-country comparison of paid activity and streaming."""

from __future__ import annotations

import pandas as pd

from lollie.analysis.baseline import (
    AnalysisSettings,
    WindowAnalysis,
    aggregate_daily,
    analyze_campaign_window,
    label_change,
)
from lollie.analysis.campaigns import campaign_dates
from lollie.analysis.relationships import (
    NONE, POSITIVE, WEAK, Relationship, lag_relationship, rank_relationship, spend_series,
)
from lollie.geo import ALL_MARKETS_CODE, market_label

MIN_OVERALL_CHANGE = 0.05
PAID = "Paid"
LOW = "Reference only"

MARKET_COLUMNS = [
    "Market", "market_code", "Paid activity", "Ad spend", "Impressions", "Clicks", "Landing page views",
    "Avg daily streams before", "Avg daily streams during", "Avg daily streams after",
    "Observed change (streams)", "Change vs baseline", "Reading", "Streaming data coverage",
    "Spend and streaming pattern", "Notes",
]


def _sum(series: pd.Series) -> float:
    return float(series.sum()) if series.notna().any() else float("nan")


def market_comparison(
    paid: pd.DataFrame,
    daily: pd.DataFrame,
    campaign_start: pd.Timestamp,
    campaign_end: pd.Timestamp,
    settings: AnalysisSettings,
    *,
    low_paid_share: float = 0.02,
) -> tuple[pd.DataFrame, dict[str, WindowAnalysis], dict[str, Relationship]]:
    """One row per country found in the paid or streaming data.

    Countries with little or no paid activity are listed for reference. They are
    never treated as a control group: they can differ from paid countries in size,
    release timing, playlisting and many other ways.
    """
    paid_codes = {c for c in paid["market_code"].dropna().unique() if c != ALL_MARKETS_CODE} if not paid.empty else set()
    stream_codes = {c for c in daily["market_code"].dropna().unique() if c != ALL_MARKETS_CODE} if not daily.empty else set()
    total_spend = float(paid["spend"].sum()) if not paid.empty and paid["spend"].notna().any() else 0.0

    rows, analyses, relationships = [], {}, {}
    for code in sorted(paid_codes | stream_codes):
        mine = paid[paid["market_code"] == code] if not paid.empty else paid
        dates = campaign_dates(mine) if not mine.empty else None
        start = dates.start if dates and dates.known else campaign_start
        end = dates.end if dates and dates.known else campaign_end
        spend = _sum(mine["spend"]) if not mine.empty else float("nan")
        share = (0.0 if pd.isna(spend) else spend) / total_spend if total_spend else 0.0
        activity = PAID if pd.notna(spend) and spend > 0 and share >= low_paid_share else LOW

        series, notes = aggregate_daily(daily, [code])
        analysis = analyze_campaign_window(series, start, end, settings) if not series.empty else None
        relation = Relationship()
        if analysis is not None:
            analyses[code] = analysis
            if activity == PAID:
                spend_daily = spend_series(mine, start, end)
                frame = analysis.series.set_index("date")
                relation = lag_relationship(spend_daily, frame["actual"], frame["expected"])
                pct = analysis.pct_change
                if relation.label in (POSITIVE, WEAK) and (pct is None or pct < MIN_OVERALL_CHANGE):
                    relation = Relationship(
                        NONE, relation.best_lag, relation.correlation, relation.paired_days, relation.by_lag,
                        "Day-to-day movement lined up with spend, but streams during the campaign were not above baseline overall.",
                    )
                relationships[code] = relation
                if relation.note:
                    notes = notes + [relation.note]
        else:
            notes = notes + ["No streaming data for this country."]
        if mine.empty and activity == LOW:
            notes = notes + ["No paid activity reported in this country."]
        if analysis is not None:
            notes = notes + analysis.flags[:2]

        rows.append(
            {
                "Market": market_label(code),
                "market_code": code,
                "Paid activity": activity,
                "Ad spend": spend,
                "Impressions": _sum(mine["impressions"]) if not mine.empty else float("nan"),
                "Clicks": _sum(mine["clicks"]) if not mine.empty else float("nan"),
                "Landing page views": _sum(mine["landing_page_views"]) if not mine.empty else float("nan"),
                "Avg daily streams before": analysis.baseline.average if analysis else None,
                "Avg daily streams during": analysis.during.average if analysis else None,
                "Avg daily streams after": analysis.post.average if analysis else None,
                "Observed change (streams)": analysis.observed_change if analysis else None,
                "Change vs baseline": analysis.pct_change if analysis else None,
                "Reading": label_change(analysis.pct_change) if analysis else "No streaming data",
                "Streaming data coverage": analysis.during.coverage if analysis else None,
                "Spend and streaming pattern": relation.label if activity == PAID else "Not assessed",
                "Notes": " ".join(notes),
            }
        )
    table = pd.DataFrame(rows, columns=MARKET_COLUMNS)
    if table.empty:
        return table, analyses, relationships
    table["_spend"] = table["Ad spend"].fillna(0)
    table["_streams"] = table["Avg daily streams before"].fillna(0)
    table = table.sort_values(["_spend", "_streams"], ascending=False).drop(columns=["_spend", "_streams"]).reset_index(drop=True)
    return table, analyses, relationships


def market_rank_note(table: pd.DataFrame) -> str | None:
    """Do countries with more spend also show larger streaming change? Descriptive only."""
    if table.empty:
        return None
    paid_rows = table[table["Paid activity"] == PAID]
    rho, n = rank_relationship(paid_rows["Ad spend"], paid_rows["Change vs baseline"])
    if rho is None:
        return None
    if rho >= 0.5:
        reading = "Countries with higher spend also tended to show a larger change versus baseline"
    elif rho <= -0.3:
        reading = "Countries with higher spend tended to show a smaller change versus baseline"
    else:
        reading = "There was no clear link between how much was spent in a country and its change versus baseline"
    return f"{reading} (rank correlation {rho:+.2f} across {n} countries). With so few countries this is a rough guide only."

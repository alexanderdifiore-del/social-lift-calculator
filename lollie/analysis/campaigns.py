"""Campaign dates, overlapping campaigns, and comparison across campaigns."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from lollie.analysis.baseline import (
    AnalysisSettings,
    WindowAnalysis,
    aggregate_daily,
    analyze_campaign_window,
    baseline_window,
)
from lollie.geo import ALL_MARKETS_CODE


@dataclass
class CampaignDates:
    start: pd.Timestamp | None
    end: pd.Timestamp | None
    inferred: bool
    note: str = ""

    @property
    def known(self) -> bool:
        return self.start is not None and self.end is not None


def campaign_dates(rows: pd.DataFrame) -> CampaignDates:
    """Start / end from the report's own campaign dates, else the first / last reporting day."""
    if rows.empty:
        return CampaignDates(None, None, False, "No paid media rows for this selection.")
    starts, ends = rows["start_date"].dropna(), rows["end_date"].dropna()
    reported = rows["date"].dropna()
    spend_days = rows.loc[rows["spend"].fillna(0) > 0, "date"].dropna()
    explicit_start, explicit_end = not starts.empty, not ends.empty
    start = starts.min() if explicit_start else (spend_days.min() if not spend_days.empty else (reported.min() if not reported.empty else pd.NaT))
    end = ends.max() if explicit_end else (spend_days.max() if not spend_days.empty else (reported.max() if not reported.empty else pd.NaT))
    if pd.isna(start) or pd.isna(end):
        return CampaignDates(None, None, True, "The paid media file has no campaign dates or dated rows.")
    note = ""
    if not (explicit_start and explicit_end):
        note = "Campaign dates were not in the report, so the first and last days with reporting are used."
    return CampaignDates(start.normalize(), end.normalize(), not (explicit_start and explicit_end), note)


def campaign_flights(paid: pd.DataFrame) -> pd.DataFrame:
    """One row per campaign and market with its start and end."""
    rows = []
    for (campaign, market_code), group in paid.groupby(["campaign_name", "market_code"], dropna=False):
        dates = campaign_dates(group)
        if not dates.known:
            continue
        rows.append(
            {
                "campaign": campaign,
                "market_code": market_code if isinstance(market_code, str) else None,
                "start": dates.start,
                "end": dates.end,
                "promoted_item": ", ".join(sorted(group["promoted_item"].dropna().astype(str).unique())[:3]),
            }
        )
    return pd.DataFrame(rows, columns=["campaign", "market_code", "start", "end", "promoted_item"])


def overlap_notes(
    paid: pd.DataFrame,
    campaign: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    settings: AnalysisSettings,
    market_codes: list[str] | None = None,
) -> list[str]:
    """Other campaigns running in the same countries during the baseline, campaign or post windows."""
    flights = campaign_flights(paid)
    if flights.empty:
        return []
    others = flights[flights["campaign"] != campaign]
    if others.empty:
        return []
    if market_codes:
        others = others[others["market_code"].isin(market_codes) | others["market_code"].isna() | (others["market_code"] == ALL_MARKETS_CODE)]
    b_start, b_end = baseline_window(start, settings)
    p_end = end + pd.Timedelta(days=settings.post_days)
    notes: list[str] = []
    for name, group in others.groupby("campaign"):
        first, last = group["start"].min(), group["end"].max()
        item = group["promoted_item"].iloc[0]
        suffix = f" (promoting {item})" if item else ""
        if first <= end and last >= start:
            notes.append(
                f"Overlapping campaign: '{name}'{suffix} ran {first:%b %d} to {last:%b %d} at the same time. "
                "Streaming change in this period may reflect both campaigns."
            )
        elif first <= b_end and last >= b_start:
            notes.append(
                f"Baseline contains another campaign: '{name}'{suffix} ran {first:%b %d} to {last:%b %d}, before this one. "
                "The baseline may already include paid activity."
            )
        elif first <= p_end and last >= end:
            notes.append(f"Another campaign, '{name}'{suffix}, started {first:%b %d}, during the after-campaign period.")
    return notes


def campaign_comparison(
    paid: pd.DataFrame,
    daily: pd.DataFrame,
    settings: AnalysisSettings,
) -> tuple[pd.DataFrame, dict[str, WindowAnalysis]]:
    """Same analysis for every campaign, in the countries where that campaign advertised."""
    columns = [
        "Campaign", "Start", "End", "Ad spend", "Landing page views", "Avg daily streams before", "Avg daily streams during",
        "Avg daily streams after", "Change vs baseline", "Observed change (streams)", "Streaming data coverage", "Baseline",
    ]
    rows, analyses = [], {}
    for campaign, group in paid.groupby("campaign_name"):
        dates = campaign_dates(group)
        if not dates.known:
            continue
        codes = sorted({c for c in group["market_code"].dropna().unique() if c != ALL_MARKETS_CODE})
        series, _ = aggregate_daily(daily, codes if codes else None)
        if series.empty:
            continue
        analysis = analyze_campaign_window(series, dates.start, dates.end, settings)
        analyses[campaign] = analysis
        rows.append(
            {
                "Campaign": campaign,
                "Start": dates.start,
                "End": dates.end,
                "Ad spend": group["spend"].sum() if group["spend"].notna().any() else None,
                "Landing page views": group["landing_page_views"].sum() if group["landing_page_views"].notna().any() else None,
                "Avg daily streams before": analysis.baseline.average,
                "Avg daily streams during": analysis.during.average,
                "Avg daily streams after": analysis.post.average,
                "Change vs baseline": analysis.pct_change,
                "Observed change (streams)": analysis.observed_change,
                "Streaming data coverage": analysis.during.coverage,
                "Baseline": analysis.method,
            }
        )
    table = pd.DataFrame(rows, columns=columns)
    return table.sort_values("Start").reset_index(drop=True) if not table.empty else table, analyses


def repeated_pattern_note(table: pd.DataFrame) -> str | None:
    """Plain statement about whether several campaigns show the same direction of change."""
    valid = table["Change vs baseline"].dropna() if not table.empty else pd.Series(dtype=float)
    if len(valid) < 2:
        return None
    up, down = int((valid >= 0.10).sum()), int((valid <= -0.10).sum())
    flat = len(valid) - up - down
    text = f"Across {len(valid)} campaigns with a usable baseline, streaming was at least 10% above baseline during {up}, at least 10% below during {down}, and within 10% during {flat}."
    if up == len(valid):
        text += " The same direction in every campaign is a pattern worth checking, but it does not show the ads caused it."
    return text

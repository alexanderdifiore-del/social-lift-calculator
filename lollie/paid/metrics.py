"""Paid media KPIs, budget pacing, goal forecasting and market breakdown.

Delivery metrics (CPM, CPC, CTR) always use gross media spend. Result metrics
(landing page views, video views, clicks, engagements) are never added together.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from lollie.paid.schema import RESULT_FAMILIES

STATUS_AHEAD = "Ahead of goal"
STATUS_ON_TRACK = "On track"
STATUS_AT_RISK = "At risk"
STATUS_UNAVAILABLE = "Forecast unavailable"


@dataclass(frozen=True)
class Thresholds:
    """Forecast attainment cut-offs (share of goal). Configurable in the UI."""

    ahead: float = 1.10
    on_track: float = 0.90


def safe_div(numerator, denominator) -> float | None:
    if numerator is None or denominator is None:
        return None
    if pd.isna(numerator) or pd.isna(denominator) or denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def cpm(spend, impressions) -> float | None:
    value = safe_div(spend, impressions)
    return None if value is None else value * 1000


def cpc(spend, clicks) -> float | None:
    return safe_div(spend, clicks)


def ctr(clicks, impressions) -> float | None:
    return safe_div(clicks, impressions)


def cost_per_result(spend, results) -> float | None:
    return safe_div(spend, results)


def result_rate(results, impressions) -> float | None:
    return safe_div(results, impressions)


def _sum(series: pd.Series) -> float | None:
    """Sum that stays None when the metric was never reported."""
    return None if series.notna().sum() == 0 else float(series.sum())


def campaign_budget_total(frame: pd.DataFrame) -> float | None:
    """Total budget counted once per campaign x market (not once per daily row)."""
    if frame["budget"].notna().sum() == 0:
        return None
    per_campaign = frame.groupby(["platform", "campaign_name", "market"])["budget"].max()
    return float(per_campaign.sum())


def aggregate_kpis(frame: pd.DataFrame) -> dict:
    """Top-line KPIs for a (single-currency) selection of campaign rows."""
    impressions = _sum(frame["impressions"])
    clicks = _sum(frame["clicks"])
    spend = _sum(frame["spend"])
    return {
        "impressions": impressions,
        "views": _sum(frame["views"]),
        "engagements": _sum(frame["engagements"]),
        "clicks": clicks,
        "spend": spend,
        "budget": campaign_budget_total(frame),
        "cpm": cpm(spend, impressions),
        "cpc": cpc(spend, clicks),
        "ctr": ctr(clicks, impressions),
        "campaigns": int(frame.groupby(["platform", "campaign_name"]).ngroups),
    }


def results_by_type(frame: pd.DataFrame) -> pd.DataFrame:
    """Results, spend and cost per result for each result type, kept separate."""
    rows = []
    for family, group in frame[frame["results"].notna()].groupby("result_family"):
        results = float(group["results"].sum())
        spend = float(group["spend"].sum())
        goal = _goal_total(group)
        rows.append(
            {
                "Result type": RESULT_FAMILIES.get(family, family),
                "family": family,
                "Results": results,
                "Goal": goal,
                "Spend": spend,
                "Cost per result": cost_per_result(spend, results),
                "Result rate": result_rate(results, group["impressions"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _goal_total(frame: pd.DataFrame) -> float | None:
    if frame["results_goal"].notna().sum() == 0:
        return None
    per_campaign = frame.groupby(["platform", "campaign_name", "market"])["results_goal"].max()
    return float(per_campaign.sum())


def forecast_attainment(
    results: float | None,
    goal: float | None,
    elapsed_days: int | None,
    total_days: int | None,
    finished: bool,
) -> float | None:
    """Projected (or final) share of goal. None when it cannot be calculated."""
    if results is None or goal is None or pd.isna(results) or pd.isna(goal) or goal <= 0:
        return None
    if finished:
        return float(results) / float(goal)
    if not total_days or not elapsed_days or elapsed_days <= 0:
        return None
    return (float(results) / elapsed_days * total_days) / float(goal)


def classify_status(attainment: float | None, thresholds: Thresholds = Thresholds()) -> str:
    if attainment is None:
        return STATUS_UNAVAILABLE
    if attainment >= thresholds.ahead:
        return STATUS_AHEAD
    if attainment >= thresholds.on_track:
        return STATUS_ON_TRACK
    return STATUS_AT_RISK


def budget_pacing(
    spend: float | None,
    budget: float | None,
    elapsed_days: int | None,
    total_days: int | None,
) -> float | None:
    """Spend ratio vs an even-spend plan. 1.0 means exactly on pace."""
    if spend is None or budget is None or budget <= 0 or not total_days or not elapsed_days:
        return None
    expected = budget * min(elapsed_days / total_days, 1.0)
    return safe_div(spend, expected)


def pacing_label(pacing: float | None) -> str:
    if pacing is None:
        return "Pacing unavailable"
    if pacing > 1.10:
        return "Ahead of plan"
    if pacing < 0.90:
        return "Behind plan"
    return "On pace"


def campaign_timing(group: pd.DataFrame, as_of: pd.Timestamp) -> dict:
    """Flight start/end, elapsed/remaining days and delivery status from the data."""
    starts = group["start_date"].dropna()
    ends = group["end_date"].dropna()
    dated = group["date"].dropna()
    start = starts.min() if not starts.empty else (dated.min() if not dated.empty else pd.NaT)
    end = ends.max() if not ends.empty else pd.NaT

    elapsed = total = remaining = None
    status = "Unknown"
    if pd.notna(start):
        elapsed = max((as_of.normalize() - start.normalize()).days + 1, 1)
        if as_of < start:
            status = "Scheduled"
        if pd.notna(end):
            total = max((end.normalize() - start.normalize()).days + 1, 1)
            remaining = max((end.normalize() - as_of.normalize()).days, 0)
            elapsed = min(elapsed, total)
            status = "Ended" if as_of.normalize() > end.normalize() else ("Scheduled" if as_of < start else "Active")
        elif status != "Scheduled":
            status = "Active"
    reported = group["status"].dropna()
    if not reported.empty:
        status = str(reported.iloc[-1]).title()
    finished = pd.notna(end) and as_of.normalize() > end.normalize()
    return {
        "start": start,
        "end": end,
        "elapsed": elapsed,
        "total": total,
        "remaining": remaining,
        "status": status,
        "finished": bool(finished),
    }


def overall_pacing(frame: pd.DataFrame, as_of: pd.Timestamp) -> float | None:
    """Spend-weighted pacing across campaigns that have both a budget and flight dates."""
    spend_total = expected_total = 0.0
    counted = False
    for _, group in frame.groupby(["platform", "campaign_name", "market"]):
        budget = group["budget"].max()
        timing = campaign_timing(group, as_of)
        if pd.isna(budget) or budget <= 0 or not timing["total"] or not timing["elapsed"]:
            continue
        counted = True
        spend_total += float(group["spend"].sum())
        expected_total += float(budget) * min(timing["elapsed"] / timing["total"], 1.0)
    return safe_div(spend_total, expected_total) if counted else None


def campaign_market_table(
    frame: pd.DataFrame,
    as_of: pd.Timestamp,
    thresholds: Thresholds = Thresholds(),
) -> pd.DataFrame:
    """One row per campaign x market x result type."""
    rows = []
    group_cols = ["platform", "campaign_name", "market"]
    for (platform, campaign, market), campaign_rows in frame.groupby(group_cols):
        timing = campaign_timing(campaign_rows, as_of)
        budget = campaign_rows["budget"].max()
        budget = None if pd.isna(budget) else float(budget)
        spend = _sum(campaign_rows["spend"])
        impressions = _sum(campaign_rows["impressions"])
        objectives = campaign_rows["objective"].dropna()
        objective = objectives.iloc[0] if not objectives.empty else "Not provided"
        pacing = budget_pacing(spend, budget, timing["elapsed"], timing["total"])

        families = campaign_rows.loc[campaign_rows["results"].notna(), "result_family"].dropna().unique()
        if len(families) == 0:
            families = [None]
        for family in families:
            subset = campaign_rows if family is None else campaign_rows[campaign_rows["result_family"] == family]
            results = _sum(subset["results"]) if family is not None else None
            goal = subset["results_goal"].max()
            goal = None if pd.isna(goal) else float(goal)
            attainment = forecast_attainment(
                results, goal, timing["elapsed"], timing["total"], timing["finished"]
            )
            sub_spend = _sum(subset["spend"])
            sub_impr = _sum(subset["impressions"])
            rows.append(
                {
                    "Campaign": campaign,
                    "Platform": platform,
                    "Market": market,
                    "Objective": objective,
                    "Result type": RESULT_FAMILIES.get(family, "Not reported") if family else "Not reported",
                    "Budget": budget,
                    "Spend": spend,
                    "Pacing": pacing,
                    "Days remaining": timing["remaining"],
                    "Results": results,
                    "Results goal": goal,
                    "Forecast attainment": attainment,
                    "CPM": cpm(sub_spend, sub_impr),
                    "Cost per result": cost_per_result(sub_spend, results),
                    "Result rate": result_rate(results, sub_impr),
                    "Campaign status": timing["status"],
                    "Goal status": classify_status(attainment, thresholds),
                    "Impressions": impressions,
                    "Clicks": _sum(campaign_rows["clicks"]),
                    "Currency": campaign_rows["currency"].iloc[0],
                }
            )
    table = pd.DataFrame(rows)
    return table.sort_values(["Platform", "Campaign", "Market"]).reset_index(drop=True) if not table.empty else table


def status_counts(table: pd.DataFrame) -> dict[str, int]:
    if table.empty:
        return {}
    return table["Goal status"].value_counts().to_dict()


def as_of_default(frame: pd.DataFrame) -> pd.Timestamp:
    dates = frame["date"].dropna()
    return dates.max().normalize() if not dates.empty else pd.Timestamp.today().normalize()


def rate_pct(value: float | None) -> str:
    return "n/a" if value is None or (isinstance(value, float) and np.isnan(value)) else f"{value * 100:.2f}%"

"""Audience and creative comparisons using only compatible metrics.

* Cost-per-result comparisons are made within one result type
  (e.g. landing page views vs landing page views).
* Engagement-rate comparisons are made within one platform, because each
  platform defines "engagement" differently.
"""

from __future__ import annotations

import pandas as pd

from lollie.paid.metrics import cost_per_result, result_rate
from lollie.paid.schema import RESULT_FAMILIES

DIMENSIONS = {"audience": "Audience", "creative": "Creative"}


def rank_dimension(frame: pd.DataFrame, dimension: str, *, min_impressions: float = 1000) -> pd.DataFrame:
    """Aggregate by audience or creative; excludes rows below a noise floor."""
    if dimension not in DIMENSIONS:
        raise ValueError("dimension must be 'audience' or 'creative'")
    data = frame[frame[dimension].notna()]
    if data.empty:
        return pd.DataFrame()

    rows = []
    for (platform, name, family), group in data.groupby(["platform", dimension, "result_family"], dropna=False):
        impressions = float(group["impressions"].sum()) if group["impressions"].notna().any() else None
        if impressions is None or impressions < min_impressions:
            continue
        spend = float(group["spend"].sum()) if group["spend"].notna().any() else None
        results = float(group["results"].sum()) if group["results"].notna().any() else None
        engagements = float(group["engagements"].sum()) if group["engagements"].notna().any() else None
        rows.append(
            {
                DIMENSIONS[dimension]: name,
                "Platform": platform,
                "family": family if isinstance(family, str) else None,
                "Result type": RESULT_FAMILIES.get(family, "Not reported") if isinstance(family, str) else "Not reported",
                "Spend": spend,
                "Impressions": impressions,
                "Results": results,
                "Engagements": engagements,
                "Cost per result": cost_per_result(spend, results),
                "Result rate": result_rate(results, impressions),
                "Engagement rate": (engagements / impressions) if engagements is not None and impressions else None,
                "Currency": group["currency"].iloc[0],
            }
        )
    return pd.DataFrame(rows)


def best_cost_effective(ranking: pd.DataFrame, result_family: str | None = None) -> pd.Series | None:
    """Lowest cost per result within a single result type."""
    if ranking.empty:
        return None
    pool = ranking[ranking["Cost per result"].notna() & ranking["family"].notna()]
    if result_family:
        pool = pool[pool["family"] == result_family]
    elif pool["family"].nunique() > 1:
        return None
    if pool.empty:
        return None
    if pool["Currency"].nunique() > 1:
        return None
    return pool.sort_values("Cost per result").iloc[0]


def best_engaging(ranking: pd.DataFrame, platform: str | None = None) -> pd.Series | None:
    """Highest engagement rate within one platform."""
    if ranking.empty:
        return None
    pool = ranking[ranking["Engagement rate"].notna()]
    if platform:
        pool = pool[pool["Platform"] == platform]
    elif pool["Platform"].nunique() > 1:
        return None
    if pool.empty:
        return None
    return pool.sort_values("Engagement rate", ascending=False).iloc[0]


def best_result_rate(ranking: pd.DataFrame, result_family: str | None = None) -> pd.Series | None:
    """Highest result rate within a single result type."""
    if ranking.empty:
        return None
    pool = ranking[ranking["Result rate"].notna() & ranking["family"].notna()]
    if result_family:
        pool = pool[pool["family"] == result_family]
    elif pool["family"].nunique() > 1:
        return None
    if pool.empty:
        return None
    return pool.sort_values("Result rate", ascending=False).iloc[0]


def comparable_result_families(ranking: pd.DataFrame) -> list[str]:
    if ranking.empty:
        return []
    return [f for f in ranking["family"].dropna().unique().tolist()]

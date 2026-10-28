"""Descriptive links between daily ad spend and daily streaming change.

These are correlations over a handful of days. They show whether two lines moved
together, not whether one caused the other.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MAX_LAG_DAYS = 7
MIN_PAIRED_DAYS = 14

POSITIVE = "Potential positive relationship"
WEAK = "Weak positive pattern"
NEGATIVE = "Negative pattern"
NONE = "No clear relationship"
UNAVAILABLE = "Not enough data"


@dataclass
class Relationship:
    label: str = UNAVAILABLE
    best_lag: int | None = None
    correlation: float | None = None
    paired_days: int = 0
    by_lag: dict[int, float] = field(default_factory=dict)
    note: str = ""


def classify(correlation: float | None) -> str:
    if correlation is None or np.isnan(correlation):
        return UNAVAILABLE
    if correlation >= 0.5:
        return POSITIVE
    if correlation >= 0.3:
        return WEAK
    if correlation <= -0.3:
        return NEGATIVE
    return NONE


def spend_series(paid: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """Daily spend across the campaign. A day inside the reported range with no row counts as no spend."""
    dated = paid[paid["date"].notna() & paid["spend"].notna()]
    if dated.empty:
        return pd.Series(dtype=float)
    daily = dated.groupby(dated["date"].dt.normalize())["spend"].sum()
    first, last = max(daily.index.min(), start), min(daily.index.max(), end)
    if first > last:
        return pd.Series(dtype=float)
    return daily.reindex(pd.date_range(first, last), fill_value=0.0)


def lag_relationship(spend: pd.Series, actual: pd.Series, expected: pd.Series, max_lag: int = MAX_LAG_DAYS) -> Relationship:
    """Correlate spend on day t with streaming change (actual - expected) on day t + lag."""
    if spend.empty or actual.dropna().empty:
        return Relationship(note="Daily spend or streaming data is missing.")
    change = (actual - expected).dropna()
    best: tuple[int, float, int] | None = None
    by_lag: dict[int, float] = {}
    for lag in range(0, max_lag + 1):
        shifted = change.copy()
        shifted.index = shifted.index - pd.Timedelta(days=lag)
        pair = pd.concat([spend.rename("spend"), shifted.rename("change")], axis=1, join="inner").dropna()
        if len(pair) < MIN_PAIRED_DAYS or pair["spend"].std() == 0 or pair["change"].std() == 0:
            continue
        r = float(pair["spend"].corr(pair["change"]))
        by_lag[lag] = r
        if best is None or r > best[1]:
            best = (lag, r, len(pair))
    if best is None:
        return Relationship(note=f"Fewer than {MIN_PAIRED_DAYS} days with both spend and streaming data, or spend did not vary.")
    lag, r, n = best
    note = ""
    if lag > 0 and r >= 0.3:
        note = f"Streaming change lines up best {lag} day(s) after spend."
    return Relationship(classify(r), lag, r, n, by_lag, note)


def rank_relationship(spend: pd.Series, change: pd.Series) -> tuple[float | None, int]:
    """Spearman-style rank correlation between markets (needs at least 4 markets)."""
    pair = pd.concat([spend.rename("spend"), change.rename("change")], axis=1).dropna()
    pair = pair[pair["spend"] > 0]
    if len(pair) < 4 or pair["spend"].nunique() < 2 or pair["change"].nunique() < 2:
        return None, len(pair)
    ranks = pair.rank()
    return float(ranks["spend"].corr(ranks["change"])), len(pair)

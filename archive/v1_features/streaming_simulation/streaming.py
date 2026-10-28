"""Streaming baseline, social-lift and impact-window math (original Lollie model).

Lift is an observational / modeled estimate: actual streams minus an expected
baseline. It is not proof that any single post or ad caused the difference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

DAILY_THRESHOLD = pd.Timedelta(hours=20)


def daily_rhythm(hour: int) -> float:
    """Hour-of-day weight for simulated baseline curves."""
    if 0 <= hour <= 5:
        return 0.55
    if 6 <= hour <= 9:
        return 0.85
    if 10 <= hour <= 15:
        return 1.0
    if 16 <= hour <= 20:
        return 1.45
    return 1.2


def simulate_baseline(
    post_timestamp: datetime,
    analysis_days: int,
    *,
    tier_multiplier: float,
    market_multiplier: float,
    dsp_multiplier: float,
    seed: int = 42,
) -> pd.DataFrame:
    """Hourly simulated expected-baseline streams (DEMO data only)."""
    hours = analysis_days * 24
    start_time = post_timestamp - timedelta(days=analysis_days // 2)
    timestamps = pd.date_range(start=start_time, periods=hours, freq="h")
    rng = np.random.RandomState(seed)

    values = []
    for ts in timestamps:
        base = 2800.0
        base *= daily_rhythm(ts.hour)
        base *= tier_multiplier
        base *= market_multiplier
        base *= dsp_multiplier
        base += rng.normal(0, 180)
        values.append(max(base, 500))

    frame = pd.DataFrame({"timestamp": timestamps, "expected_baseline_streams": values})
    frame["actual_streams"] = frame["expected_baseline_streams"].copy()
    return frame


def apply_social_lift(
    dataframe: pd.DataFrame,
    event_time: datetime,
    impact_window_hours: int,
    *,
    campaign_intensity: float,
    platform_multiplier: float,
    post_type_multiplier: float,
    strength_multiplier: float = 1.0,
) -> pd.DataFrame:
    """Apply a decaying simulated lift to actual_streams (DEMO data only)."""
    result = dataframe.copy()
    mask = (result["timestamp"] >= event_time) & (
        result["timestamp"] < event_time + timedelta(hours=impact_window_hours)
    )
    n = int(mask.sum())
    if n == 0:
        return result

    starting_lift = (
        1.4
        + campaign_intensity * 0.22
        + platform_multiplier * 0.25
        + post_type_multiplier * 0.3
    ) * strength_multiplier
    ending_lift = 1.05
    decay_curve = np.linspace(starting_lift, ending_lift, n)
    result.loc[mask, "actual_streams"] = result.loc[mask, "actual_streams"].values * decay_curve
    return result


def detect_granularity(timestamps: pd.Series) -> str:
    """Return ``"daily"`` or ``"intraday"`` from the source's real spacing."""
    ts = pd.to_datetime(timestamps, errors="coerce").dropna().sort_values().drop_duplicates()
    if len(ts) < 2:
        return "intraday"
    median_gap = ts.diff().dropna().median()
    return "daily" if median_gap >= DAILY_THRESHOLD else "intraday"


def granularity_label(granularity: str) -> str:
    return "Daily Streams" if granularity == "daily" else "Hourly Streams"


def impact_window_mask(
    timestamps: pd.Series,
    post_timestamp: datetime,
    impact_window_hours: int,
    granularity: str = "intraday",
) -> pd.Series:
    """Rows inside the impact window.

    Intraday data uses exact timestamps. Daily data is measured in whole days
    starting on the post date, because a daily row cannot be split by hour.
    """
    ts = pd.to_datetime(timestamps)
    if granularity == "daily":
        post_day = pd.Timestamp(post_timestamp).normalize()
        days = max(int(np.ceil(impact_window_hours / 24)), 1)
        day = ts.dt.normalize()
        return (day >= post_day) & (day < post_day + pd.Timedelta(days=days))
    end = post_timestamp + timedelta(hours=impact_window_hours)
    return (ts >= post_timestamp) & (ts < end)


def estimate_baseline(
    actuals: pd.DataFrame,
    post_timestamp: datetime,
    impact_window_hours: int,
    granularity: str = "intraday",
) -> pd.Series:
    """Estimate an expected baseline from the uploaded data's own history.

    Excludes the impact window. Intraday data uses a median hour-of-day
    profile (original behavior). Daily data uses a median weekday profile when
    at least two weeks of history exist, otherwise the overall median.
    """
    in_window = impact_window_mask(
        actuals["timestamp"], post_timestamp, impact_window_hours, granularity
    )
    history = actuals.loc[~in_window]
    overall = actuals["actual_streams"].median() if history.empty else history["actual_streams"].median()

    if history.empty:
        return pd.Series(overall, index=actuals.index, dtype=float)

    if granularity == "daily":
        if len(history) >= 14:
            profile = history.groupby(history["timestamp"].dt.day_of_week)["actual_streams"].median()
            return actuals["timestamp"].dt.day_of_week.map(profile).fillna(overall).astype(float)
        return pd.Series(overall, index=actuals.index, dtype=float)

    profile = history.groupby(history["timestamp"].dt.hour)["actual_streams"].median()
    return actuals["timestamp"].dt.hour.map(profile).fillna(overall).astype(float)


@dataclass(frozen=True)
class ImpactSummary:
    expected: float
    actual: float
    lift: float
    lift_percent: float | None
    baseline_rate: float


def summarize_impact(frame: pd.DataFrame, mask: pd.Series) -> ImpactSummary:
    expected = float(frame.loc[mask, "expected_baseline_streams"].sum())
    actual = float(frame.loc[mask, "actual_streams"].sum())
    lift = actual - expected
    return ImpactSummary(
        expected=expected,
        actual=actual,
        lift=lift,
        lift_percent=(lift / expected * 100) if expected > 0 else None,
        baseline_rate=float(frame["expected_baseline_streams"].mean()),
    )


@dataclass
class StreamingPrep:
    frame: pd.DataFrame
    granularity: str = "intraday"
    notes: list[str] = field(default_factory=list)
    baseline_estimated: bool = False
    error: str | None = None


def prepare_streaming_frame(
    raw: pd.DataFrame,
    timestamp_column: str,
    actual_column: str,
    baseline_column: str | None,
    *,
    post_timestamp: datetime,
    impact_window_hours: int,
    market_column: str | None = None,
    market: str | None = None,
) -> StreamingPrep:
    """Turn an uploaded streaming table into the dashboard frame.

    Uses only what the file contains: the real time spacing is detected (hourly
    vs daily) and a baseline is estimated from the file's own history when none
    is supplied. Nothing is interpolated or invented.
    """
    notes: list[str] = []
    if timestamp_column == actual_column:
        return StreamingPrep(pd.DataFrame(), error="The timestamp column and the actual streams column cannot be the same column.")
    if baseline_column in (timestamp_column, actual_column):
        return StreamingPrep(pd.DataFrame(), error="The expected baseline column must be different from the timestamp and actual streams columns.")

    working = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                raw[timestamp_column].astype(str).str.replace("\n", " ", regex=False).str.replace("\r", " ", regex=False),
                errors="coerce",
            ),
            "actual_streams": pd.to_numeric(
                raw[actual_column].astype(str).str.replace(r"[,\s]", "", regex=True), errors="coerce"
            ),
        }
    )
    if baseline_column:
        working["expected_baseline_streams"] = pd.to_numeric(
            raw[baseline_column].astype(str).str.replace(r"[,\s]", "", regex=True), errors="coerce"
        )
    if market_column:
        working["market"] = raw[market_column].astype(str).str.strip()

    total_rows = len(working)
    working = working.dropna(subset=["timestamp", "actual_streams"])
    dropped = total_rows - len(working)
    if dropped:
        notes.append(f"{dropped} row(s) were skipped because the date or the streams value could not be read.")
    if working.empty:
        return StreamingPrep(
            pd.DataFrame(),
            error="No valid timestamp / stream rows were found. Check that dates look like 2026-06-17 12:00:00 and streams are numbers.",
        )

    if market_column and market and market != "All markets":
        working = working[working["market"] == market]
        if working.empty:
            return StreamingPrep(pd.DataFrame(), error=f"No streaming rows were found for market '{market}'.")

    value_columns = ["actual_streams"] + (["expected_baseline_streams"] if baseline_column else [])
    duplicated = int(working.duplicated(subset=["timestamp"]).sum())
    if duplicated:
        notes.append(
            f"{duplicated} row(s) shared a timestamp with another row (for example several markets or DSPs); "
            "they were added together."
        )
    working = working.groupby("timestamp", as_index=False)[value_columns].sum(min_count=1)
    working = working.sort_values("timestamp").reset_index(drop=True)

    granularity = detect_granularity(working["timestamp"])
    if baseline_column:
        working["expected_baseline_streams"] = working["expected_baseline_streams"].fillna(
            working["actual_streams"].median()
        )
        estimated = False
    else:
        working["expected_baseline_streams"] = estimate_baseline(
            working, post_timestamp, impact_window_hours, granularity
        )
        estimated = True
        notes.append(
            "No expected-baseline column was provided, so the baseline was estimated from the uploaded data's own "
            + ("typical day of the week" if granularity == "daily" else "typical hour of the day")
            + " outside the impact window."
        )

    frame = working[["timestamp", "expected_baseline_streams", "actual_streams"]].copy()
    post_ts = pd.Timestamp(post_timestamp)
    if post_ts < frame["timestamp"].min() or post_ts > frame["timestamp"].max() + pd.Timedelta(days=1):
        notes.append("The post date falls outside the uploaded streaming date range, so no impact window could be measured.")
    return StreamingPrep(frame, granularity, notes, estimated)


def manual_summary(expected: float, actual: float) -> ImpactSummary:
    lift = float(actual) - float(expected)
    return ImpactSummary(
        expected=float(expected),
        actual=float(actual),
        lift=lift,
        lift_percent=(lift / expected * 100) if expected > 0 else None,
        baseline_rate=0.0,
    )

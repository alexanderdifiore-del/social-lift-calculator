"""Streaming simulation helpers shared across Lollie surfaces."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from lollie.constants import (
    ARTIST_TIER_MULTIPLIER,
    MARKET_MULTIPLIER,
    PLATFORM_MULTIPLIER,
    POST_TYPE_MULTIPLIER,
)


def daily_rhythm(hour: int) -> float:
    """Hour-of-day weight for baseline streaming curves."""
    if 0 <= hour <= 5:
        return 0.55
    if 6 <= hour <= 9:
        return 0.85
    if 10 <= hour <= 15:
        return 1.0
    if 16 <= hour <= 20:
        return 1.45
    return 1.2


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
    """Apply decaying lift to actual_streams after a social or paid event."""
    result = dataframe.copy()
    impact_mask = (
        (result["timestamp"] >= event_time)
        & (result["timestamp"] < event_time + timedelta(hours=impact_window_hours))
    )
    n = int(impact_mask.sum())
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
    result.loc[impact_mask, "actual_streams"] = (
        result.loc[impact_mask, "actual_streams"].values * decay_curve
    )
    return result


def resolve_multipliers(
    *,
    artist_tier: str,
    platform: str,
    primary_market: str,
    post_type: str = "Paid boost",
    dsp_multiplier: float = 1.0,
) -> dict[str, float]:
    """Return named multipliers used in baseline and lift models."""
    return {
        "tier": ARTIST_TIER_MULTIPLIER[artist_tier],
        "platform": PLATFORM_MULTIPLIER[platform],
        "market": MARKET_MULTIPLIER[primary_market],
        "post_type": POST_TYPE_MULTIPLIER[post_type],
        "dsp": dsp_multiplier,
    }


def generate_baseline_frame(
    *,
    post_timestamp: datetime,
    analysis_days: int,
    artist_tier: str,
    platform: str,
    primary_market: str,
    dsp_multiplier: float = 1.0,
    random_seed: int = 42,
) -> pd.DataFrame:
    """Build hourly expected baseline streams before social lift is applied."""
    hours = analysis_days * 24
    start_time = post_timestamp - timedelta(days=analysis_days // 2)
    timestamps = pd.date_range(start=start_time, periods=hours, freq="h")
    mult = resolve_multipliers(
        artist_tier=artist_tier,
        platform=platform,
        primary_market=primary_market,
        dsp_multiplier=dsp_multiplier,
    )

    rng = np.random.default_rng(random_seed)
    baseline_values = []
    for ts in timestamps:
        base = 2800.0
        base *= daily_rhythm(ts.hour)
        base *= mult["tier"]
        base *= mult["market"]
        base *= mult["dsp"]
        base += rng.normal(0, 180)
        baseline_values.append(max(base, 500))

    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "expected_baseline_streams": baseline_values,
        }
    )
    frame["actual_streams"] = frame["expected_baseline_streams"].copy()
    return frame


def incremental_streams_from_lift(
    dataframe: pd.DataFrame,
    event_time: datetime,
    impact_window_hours: int,
    *,
    campaign_intensity: float,
    platform: str,
    artist_tier: str,
    primary_market: str,
    dsp_multiplier: float = 1.0,
) -> float:
    """Compare lifted actuals to baseline inside the impact window."""
    mult = resolve_multipliers(
        artist_tier=artist_tier,
        platform=platform,
        primary_market=primary_market,
        dsp_multiplier=dsp_multiplier,
    )
    lifted = apply_social_lift(
        dataframe,
        event_time,
        impact_window_hours,
        campaign_intensity=campaign_intensity,
        platform_multiplier=mult["platform"],
        post_type_multiplier=mult["post_type"],
    )
    window = lifted[
        (lifted["timestamp"] >= event_time)
        & (lifted["timestamp"] < event_time + timedelta(hours=impact_window_hours))
    ]
    expected = window["expected_baseline_streams"].sum()
    actual = window["actual_streams"].sum()
    return float(max(actual - expected, 0))

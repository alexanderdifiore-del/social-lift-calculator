"""Paid media planning and efficiency modeling for Lollie v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from lollie.constants import PAID_CHANNEL_DEFAULTS, PLATFORM_MULTIPLIER


@dataclass(frozen=True)
class ChannelAllocation:
    channel: str
    budget_usd: float
    cpm: float
    ctr: float
    view_to_stream_rate: float
    platform_multiplier: float


@dataclass(frozen=True)
class ChannelResult:
    channel: str
    budget_usd: float
    impressions: float
    clicks: float
    estimated_views: float
    estimated_incremental_streams: float
    cost_per_incremental_stream: float | None
    effective_cpm: float


@dataclass(frozen=True)
class PaidMediaPlan:
    total_budget_usd: float
    campaign_intensity: float
    artist_tier: str
    primary_market: str
    channels: tuple[ChannelResult, ...]

    @property
    def total_incremental_streams(self) -> float:
        return sum(c.estimated_incremental_streams for c in self.channels)

    @property
    def blended_cost_per_stream(self) -> float | None:
        total = self.total_incremental_streams
        if total <= 0:
            return None
        return self.total_budget_usd / total


def _normalize_weights(channel_budgets: dict[str, float]) -> dict[str, float]:
    positive = {k: max(v, 0.0) for k, v in channel_budgets.items()}
    total = sum(positive.values())
    if total <= 0:
        equal = 1.0 / len(positive) if positive else 0.0
        return {k: equal for k in positive}
    return {k: v / total for k, v in positive.items()}


def build_paid_media_plan(
    *,
    total_budget_usd: float,
    channel_budgets: dict[str, float],
    campaign_intensity: float,
    artist_tier: str,
    primary_market: str,
    channel_overrides: dict[str, dict[str, float]] | None = None,
) -> PaidMediaPlan:
    """
    Allocate spend across paid channels and estimate incremental streams.

    channel_budgets values are relative weights (percent-style inputs are fine).
    """
    overrides = channel_overrides or {}
    weights = _normalize_weights(channel_budgets)
    results: list[ChannelResult] = []

    intensity_stream_factor = 1.0 + (campaign_intensity - 1) * 0.08
    tier_stream_factor = {
        "Emerging": 0.85,
        "Mid-tier": 1.0,
        "Established": 1.12,
        "Superstar": 1.25,
    }.get(artist_tier, 1.0)
    market_stream_factor = {
        "US": 1.08,
        "Global": 1.0,
        "Europe": 1.04,
        "LATAM": 1.06,
        "APAC": 1.05,
    }.get(primary_market, 1.0)

    for channel_name, weight in weights.items():
        defaults = PAID_CHANNEL_DEFAULTS.get(channel_name)
        if defaults is None:
            continue
        custom = overrides.get(channel_name, {})
        budget = total_budget_usd * weight
        cpm = float(custom.get("cpm", defaults["default_cpm"]))
        ctr = float(custom.get("ctr", defaults["default_ctr"]))
        view_to_stream_rate = float(
            custom.get("view_to_stream_rate", defaults["view_to_stream_rate"])
        )
        platform_key = defaults["platform_key"]
        platform_multiplier = PLATFORM_MULTIPLIER.get(platform_key, 1.0)

        impressions = (budget / cpm) * 1000 if cpm > 0 else 0.0
        clicks = impressions * ctr
        estimated_views = impressions * 0.92
        raw_streams = estimated_views * view_to_stream_rate
        estimated_streams = (
            raw_streams
            * platform_multiplier
            * intensity_stream_factor
            * tier_stream_factor
            * market_stream_factor
        )
        cpis = budget / estimated_streams if estimated_streams > 0 else None

        results.append(
            ChannelResult(
                channel=channel_name,
                budget_usd=budget,
                impressions=impressions,
                clicks=clicks,
                estimated_views=estimated_views,
                estimated_incremental_streams=estimated_streams,
                cost_per_incremental_stream=cpis,
                effective_cpm=cpm,
            )
        )

    return PaidMediaPlan(
        total_budget_usd=total_budget_usd,
        campaign_intensity=campaign_intensity,
        artist_tier=artist_tier,
        primary_market=primary_market,
        channels=tuple(results),
    )


def channel_efficiency_table(plan: PaidMediaPlan) -> pd.DataFrame:
    """Format plan channel results for Streamlit tables and exports."""
    rows: list[dict[str, Any]] = []
    for channel in plan.channels:
        rows.append(
            {
                "Channel": channel.channel,
                "Budget ($)": round(channel.budget_usd, 2),
                "Impressions": int(round(channel.impressions)),
                "Est. Views": int(round(channel.estimated_views)),
                "Est. Incremental Streams": int(round(channel.estimated_incremental_streams)),
                "Cost / Incremental Stream ($)": (
                    round(channel.cost_per_incremental_stream, 4)
                    if channel.cost_per_incremental_stream is not None
                    else None
                ),
                "CPM ($)": round(channel.effective_cpm, 2),
            }
        )
    return pd.DataFrame(rows)


def recommend_budget_shift(plan: PaidMediaPlan) -> pd.DataFrame:
    """Suggest moving spend toward lower cost-per-stream channels."""
    rows = []
    blended = plan.blended_cost_per_stream
    if blended is None:
        return pd.DataFrame(columns=["Channel", "Recommendation", "Rationale"])

    for channel in plan.channels:
        cpis = channel.cost_per_incremental_stream
        if cpis is None:
            recommendation = "Hold"
            rationale = "No modeled incremental streams at current assumptions."
        elif cpis < blended * 0.85:
            recommendation = "Increase share"
            rationale = f"Cost per stream ({cpis:.3f}) beats blended average ({blended:.3f})."
        elif cpis > blended * 1.15:
            recommendation = "Decrease share"
            rationale = f"Cost per stream ({cpis:.3f}) is above blended average ({blended:.3f})."
        else:
            recommendation = "Hold"
            rationale = "Near portfolio average efficiency."
        rows.append(
            {
                "Channel": channel.channel,
                "Recommendation": recommendation,
                "Rationale": rationale,
            }
        )
    return pd.DataFrame(rows)

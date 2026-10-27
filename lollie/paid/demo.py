"""Synthetic paid-media data for Demo mode ONLY.

Never used in production mode. Every row is tagged with source_file
'DEMO (synthetic)' so it can never be mistaken for campaign reporting.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from lollie.paid.ingest import IngestResult
from lollie.paid.schema import PLATFORM_GOOGLE, PLATFORM_META, PLATFORM_TIKTOK

DEMO_SOURCE = "DEMO (synthetic)"

_CAMPAIGNS = [
    # platform, campaign, objective, result type, market, budget, goal, daily spend, audience, creative, CPM, CTR, result rate
    (PLATFORM_TIKTOK, "Demo - TikTok Creator Amplification", "Video views", "Video views", "US", 6000, 900000, 380, "Lookalike - recent listeners", "Studio version - 15s", 6.0, 0.011, 0.34),
    (PLATFORM_TIKTOK, "Demo - TikTok Creator Amplification", "Video views", "Video views", "UK", 3000, 420000, 190, "Interest - indie pop", "Studio version - 15s", 5.2, 0.010, 0.30),
    (PLATFORM_META, "Demo - Reels Release Push", "Landing page views", "Landing page views", "US", 8000, 14000, 520, "Lookalike - recent listeners", "Reel - lyric clip", 9.8, 0.014, 0.0072),
    (PLATFORM_META, "Demo - Reels Release Push", "Landing page views", "Landing page views", "BR", 4000, 11000, 210, "Interest - indie pop", "Reel - behind the scenes", 4.1, 0.016, 0.0105),
    (PLATFORM_GOOGLE, "Demo - YouTube Official Video", "Video views", "Video views", "US", 5000, 260000, 330, "Related artists - channels", "Official video - 30s", 7.4, 0.006, 0.21),
    (PLATFORM_GOOGLE, "Demo - YouTube Official Video", "Video views", "Video views", "MX", 2500, 260000, 120, "Related artists - channels", "Official video - 30s", 3.2, 0.005, 0.27),
]


def synthetic_paid_media(post_timestamp: pd.Timestamp, days: int = 14, seed: int = 7) -> IngestResult:
    rng = np.random.RandomState(seed)
    start = pd.Timestamp(post_timestamp).normalize() - pd.Timedelta(days=2)
    rows = []
    for (platform, campaign, objective, result_type, market, budget, goal, daily_spend,
         audience, creative, cpm_value, ctr_value, rate_value) in _CAMPAIGNS:
        for offset in range(days):
            day = start + pd.Timedelta(days=offset)
            spend = max(daily_spend * rng.uniform(0.8, 1.15), 1)
            impressions = spend / cpm_value * 1000
            clicks = impressions * ctr_value * rng.uniform(0.9, 1.1)
            results = impressions * rate_value * rng.uniform(0.9, 1.1)
            rows.append(
                {
                    "date": day,
                    "platform": platform,
                    "campaign_id": None,
                    "campaign_name": campaign,
                    "objective": objective,
                    "market": market,
                    "audience": audience,
                    "creative": creative,
                    "currency": "USD",
                    "result_type": result_type,
                    "status": None,
                    "artist": None,
                    "impressions": round(impressions),
                    "views": round(results) if "Video" in objective else np.nan,
                    "engagements": round(clicks * 1.8),
                    "clicks": round(clicks),
                    "spend": round(spend, 2),
                    "results": round(results),
                    "budget": budget,
                    "results_goal": goal,
                    "start_date": start,
                    "end_date": start + pd.Timedelta(days=days + 6),
                }
            )
    frame = pd.DataFrame(rows)
    from lollie.paid.schema import result_family

    frame["objective_family"] = frame["objective"].map(result_family)
    frame["result_family"] = frame["result_type"].map(result_family)
    frame["source_file"] = DEMO_SOURCE
    frame["source_priority"] = 1
    frame["reported_platform"] = frame["platform"]
    return IngestResult(frame=frame, source_label=DEMO_SOURCE, platform="Demo")

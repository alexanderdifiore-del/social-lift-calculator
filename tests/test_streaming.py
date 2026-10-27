from datetime import datetime

import pandas as pd

from lollie.streaming import (
    apply_social_lift,
    daily_rhythm,
    generate_baseline_frame,
    incremental_streams_from_lift,
)


def test_daily_rhythm_peak_evening():
    assert daily_rhythm(18) == 1.45
    assert daily_rhythm(3) == 0.55


def test_apply_social_lift_increases_actuals_in_window():
    post_time = datetime(2026, 6, 17, 18, 0, 0)
    frame = generate_baseline_frame(
        post_timestamp=post_time,
        analysis_days=7,
        artist_tier="Mid-tier",
        platform="TikTok",
        primary_market="US",
    )
    lifted = apply_social_lift(
        frame,
        post_time,
        24,
        campaign_intensity=6,
        platform_multiplier=1.65,
        post_type_multiplier=1.25,
    )
    window = lifted[
        (lifted["timestamp"] >= post_time)
        & (lifted["timestamp"] < post_time + pd.Timedelta(hours=24))
    ]
    assert window["actual_streams"].sum() > window["expected_baseline_streams"].sum()


def test_incremental_streams_non_negative():
    post_time = datetime(2026, 6, 17, 12, 0, 0)
    frame = generate_baseline_frame(
        post_timestamp=post_time,
        analysis_days=7,
        artist_tier="Established",
        platform="Instagram Reels",
        primary_market="Global",
    )
    incremental = incremental_streams_from_lift(
        frame,
        post_time,
        12,
        campaign_intensity=5,
        platform="Instagram Reels",
        artist_tier="Established",
        primary_market="Global",
    )
    assert incremental >= 0

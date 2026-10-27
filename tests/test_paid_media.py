from lollie.constants import PAID_CHANNEL_DEFAULTS
from lollie.paid_media import build_paid_media_plan, channel_efficiency_table


def test_build_plan_respects_budget_total():
    weights = {name: 25 for name in PAID_CHANNEL_DEFAULTS}
    plan = build_paid_media_plan(
        total_budget_usd=10_000,
        channel_budgets=weights,
        campaign_intensity=6,
        artist_tier="Mid-tier",
        primary_market="US",
    )
    allocated = sum(c.budget_usd for c in plan.channels)
    assert abs(allocated - 10_000) < 0.05
    assert plan.total_incremental_streams > 0


def test_channel_efficiency_table_columns():
    plan = build_paid_media_plan(
        total_budget_usd=5_000,
        channel_budgets={"TikTok Ads": 100},
        campaign_intensity=4,
        artist_tier="Emerging",
        primary_market="LATAM",
    )
    table = channel_efficiency_table(plan)
    assert "Est. Incremental Streams" in table.columns
    assert len(table) == 1

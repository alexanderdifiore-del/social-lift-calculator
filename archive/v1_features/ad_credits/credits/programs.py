"""Partner-funded ad credit programs from Global Catalog deck (in-kind, not billing coupons).

Defaults are seeded from the presentation; every field is editable in the UI —
do not treat as platform-wide rules or guaranteed public offers.
"""

from __future__ import annotations

from typing import Any

# Deck-aligned program blueprints (editable per instance)
PROGRAM_BLUEPRINTS: list[dict[str, Any]] = [
    {
        "program_key": "tiktok_platform_ad_credits",
        "platform": "TikTok Ads",
        "program_name": "TikTok Platform Ad Credits (Global Catalog)",
        "value_unit": "USD",
        "budget_model": "quarterly",
        "default_period_label": "Quarter",
        "default_budget": 186_000.0,
        "notes_template": (
            "Functions like cash in TikTok Ads Manager. Typical splits: 20k / 10k / 5k. "
            "Supports ~4 major priority projects per month plus slush fund."
        ),
        "project_criteria_hint": (
            "Trend amplification, platform moments, creator campaign amplification, "
            "TikTok account launches, major syncs, cultural tentpoles, streaming uplift."
        ),
        "source_reference": "Global Catalog Ad Credits — TikTok Platform Ad Credits",
    },
    {
        "program_key": "tiktok_rmf_promoted_sound",
        "platform": "TikTok Ads",
        "program_name": "TikTok RMF — Promoted Sound (Hot Sounds 5th slot)",
        "value_unit": "USD",
        "budget_model": "quarterly",
        "default_period_label": "Quarter",
        "default_budget": 337_300.0,
        "notes_template": (
            "Premium promoted sound placement (Sponsored). ~65 markets. "
            "Avg 100k–200k impressions per territory. Submit sound link ≥10 days before quarter end."
        ),
        "project_criteria_hint": "Viral tracks on app; typically 1–3 sounds per quarter.",
        "source_reference": "Global Catalog Ad Credits — TikTok RMF aka Promoted Sound",
    },
    {
        "program_key": "tiktok_emf_sound_banner",
        "platform": "TikTok Ads",
        "program_name": "TikTok EMF (Sound Banner 686×180)",
        "value_unit": "other",
        "budget_model": "project",
        "default_period_label": "Per placement",
        "default_budget": None,
        "notes_template": (
            "Sounds-page banner with artist name and track title. Needs artist image + preferred font. "
            "~27 countries. Single sound per asset. Constraint: TikTok must not already support "
            "the same project with an existing sound banner."
        ),
        "project_criteria_hint": "Trending sounds, seasonal tracks, syncs, pop culture moments.",
        "source_reference": "Global Catalog Ad Credits — TikTok EMF (Sound Banner)",
    },
    {
        "program_key": "spotify_platform_ad_credits",
        "platform": "Spotify",
        "program_name": "Spotify Platform Ad Credits (Global Catalog)",
        "value_unit": "share_percent",
        "budget_model": "monthly",
        "default_period_label": "Month",
        "default_budget": 45.0,  # 3 allocations × 15% share (5/5/5 split)
        "notes_template": (
            "Audio, video, and banner ads on ad-supported tier. Campaigns set up globally by "
            "local markets on our behalf. 3 allocations/month; Global Catalog 15% share of company "
            "total, typically split 5/5/5% across selected campaigns. Assets + audio script due "
            "by end of previous month."
        ),
        "project_criteria_hint": (
            "Major anniversaries, multi-platform trending tracks, major syncs, cultural moments."
        ),
        "source_reference": "Global Catalog Ad Credits — Spotify Platform Ad Credits",
    },
    {
        "program_key": "snap_coupons",
        "platform": "Snapchat Ads",
        "program_name": "Snap Coupons (1:1 match)",
        "value_unit": "USD",
        "budget_model": "capacity",
        "default_period_label": "Match capacity",
        "default_budget": 20_000.0,
        "notes_template": (
            "1:1 top-up match on cash ad spend (spend $1k → $2k total value). "
            "Current allocated capacity: match up to $20k. Extends lifespan of lenses, Snaps, creative."
        ),
        "project_criteria_hint": "Promoted lenses, Snaps, existing creative assets.",
        "source_reference": "Global Catalog Ad Credits — Snap Coupons",
    },
    {
        "program_key": "meta_promotional_fund",
        "platform": "Meta Ads",
        "program_name": "Meta Promotional Fund (Reels)",
        "value_unit": "USD",
        "budget_model": "quarterly",
        "default_period_label": "Quarter",
        "default_budget": 150_000.0,
        "notes_template": (
            "$150k quarterly for Reels content. Paid upfront by us, reimbursed by Meta. "
            "Requires internal PO explicitly naming project as part of Meta Fund. "
            "Tiers: 20k / 10k / 5k. Creator campaigns on Reels or content filming/production."
        ),
        "project_criteria_hint": (
            "Trending tracks with substantial sustained streaming lifts (ideally 1M+ incremental), "
            "priority campaigns, seasonal tracks."
        ),
        "source_reference": "Global Catalog Ad Credits — Meta Promotional Fund",
    },
    {
        "program_key": "youtube_gratis_impressions",
        "platform": "Google Ads / YouTube",
        "program_name": "YouTube Gratis Impressions (Global Catalog)",
        "value_unit": "impressions",
        "budget_model": "monthly",
        "default_period_label": "Month",
        "default_budget": 51_000_000,
        "notes_template": (
            "~51M impressions/month (fluctuates with WMG traffic share, ~5–6% return). "
            "Manually allocated by project based on track's top markets. Target via keywords + "
            "channels of related WMG artists. No assets required (video link). Served impressions "
            "are typically a fraction of committed. From the 24th, impressions count toward views."
        ),
        "project_criteria_hint": (
            "Trending tracks with sustained uplifts, official music videos, live footage, new YT content."
        ),
        "source_reference": "Global Catalog Ad Credits — YouTube Gratis Impressions",
    },
]

VALUE_UNIT_LABELS = {
    "USD": "USD value",
    "impressions": "Impressions",
    "share_percent": "Share (%) of company allocation",
    "other": "Placement / other unit",
}

BUDGET_MODEL_LABELS = {
    "quarterly": "Quarterly budget",
    "monthly": "Monthly cadence",
    "capacity": "Match / capacity cap",
    "project": "Per project / placement",
}

FUNDING_IN_KIND = "In-kind partner funding"
FUNDING_BILLING = "Billing credit"
FUNDING_PREPAID = "Prepaid funds"

# Meta's promotional fund is paid upfront by the label and reimbursed later,
# so it is shown as prepaid funds rather than as an in-kind grant.
PREPAID_PROGRAM_KEYS = {"meta_promotional_fund"}


def funding_type_for_program(program_key: str | None) -> str:
    return FUNDING_PREPAID if program_key in PREPAID_PROGRAM_KEYS else FUNDING_IN_KIND


def funding_type_for_credit(credit_category: str | None) -> str:
    return FUNDING_PREPAID if credit_category and "prepaid" in credit_category.lower() else FUNDING_BILLING

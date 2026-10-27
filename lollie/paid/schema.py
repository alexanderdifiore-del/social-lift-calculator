"""Canonical paid-media schema, column aliases and platform/objective helpers."""

from __future__ import annotations

import re

PLATFORM_META = "Meta Ads"
PLATFORM_TIKTOK = "TikTok Ads"
PLATFORM_GOOGLE = "Google Ads / YouTube"
PLATFORM_SNAP = "Snapchat Ads"
PLATFORM_WAVO = "WAVO (consolidated)"
PLATFORM_OTHER = "Other / unspecified"

PLATFORM_OPTIONS = [
    PLATFORM_META,
    PLATFORM_TIKTOK,
    PLATFORM_GOOGLE,
    PLATFORM_SNAP,
    PLATFORM_WAVO,
    PLATFORM_OTHER,
]

SOURCE_PRIORITY = {
    PLATFORM_META: 1,
    PLATFORM_TIKTOK: 1,
    PLATFORM_GOOGLE: 1,
    PLATFORM_SNAP: 1,
    PLATFORM_WAVO: 2,
    PLATFORM_OTHER: 3,
}

TEXT_FIELDS = [
    "platform",
    "campaign_id",
    "campaign_name",
    "objective",
    "market",
    "audience",
    "creative",
    "currency",
    "result_type",
    "status",
    "artist",
]
NUMERIC_FIELDS = [
    "impressions",
    "views",
    "engagements",
    "clicks",
    "spend",
    "results",
    "budget",
    "results_goal",
]
DATE_FIELDS = ["date", "start_date", "end_date"]
CANONICAL_FIELDS = DATE_FIELDS + TEXT_FIELDS + NUMERIC_FIELDS

FIELD_LABELS = {
    "date": "Date (daily)",
    "platform": "Platform",
    "campaign_id": "Campaign ID",
    "campaign_name": "Campaign name",
    "objective": "Campaign objective",
    "market": "Country / market",
    "audience": "Audience (ad set / ad group)",
    "creative": "Creative (ad name)",
    "currency": "Currency",
    "result_type": "Result type",
    "status": "Campaign status",
    "artist": "Artist",
    "impressions": "Impressions",
    "views": "Video views",
    "engagements": "Engagements",
    "clicks": "Clicks",
    "spend": "Spend",
    "results": "Results",
    "budget": "Total budget",
    "results_goal": "Results goal",
    "start_date": "Flight start",
    "end_date": "Flight end",
}

# Regex patterns tested against a normalized (snake_case) column name.
FIELD_PATTERNS: dict[str, list[str]] = {
    "date": [r"date", r"day", r"stat_time_day", r"by_day", r"report_date", r"reporting_date"],
    "platform": [r"platform", r"network", r"publisher", r"channel", r"source"],
    "campaign_id": [r"campaign_id", r"campaign_no", r"cid"],
    "campaign_name": [r"campaign_name", r"campaign", r"campaign_title"],
    "objective": [r"objective", r"campaign_objective", r"objective_type", r"campaign_goal", r"campaign_type"],
    "market": [
        r"country", r"country_region", r"country_territory", r"market", r"region",
        r"geo", r"location", r"country_territory_user_location",
    ],
    "audience": [
        r"ad_set_name", r"adset_name", r"ad_group_name", r"ad_group", r"audience",
        r"audience_name", r"targeting", r"ad_squad_name", r"ad_set",
    ],
    "creative": [r"ad_name", r"creative", r"creative_name", r"ad_creative", r"video_name", r"ad"],
    "impressions": [r"impressions", r"impression", r"impr", r"paid_impressions", r"total_impressions"],
    "views": [r"video_views", r"views", r"video_plays", r"thruplays", r"video_view"],
    "engagements": [
        r"engagements", r"post_engagements", r"total_engagements", r"interactions",
        r"engagement", r"post_engagement",
    ],
    "clicks": [r"clicks", r"link_clicks", r"clicks_all", r"swipe_ups", r"swipes", r"click", r"destination_clicks"],
    "spend": [
        r"spend", r"amount_spent.*", r"cost", r"total_spend", r"spend_.*", r"amount_spent",
    ],
    "currency": [r"currency", r"currency_code", r"account_currency"],
    "results": [r"results", r"result", r"total_results", r"conversions"],
    "result_type": [r"result_type", r"result_indicator", r"result_metric", r"optimization_goal", r"conversion_event"],
    "budget": [r"budget", r"total_budget", r"campaign_budget", r"lifetime_budget", r"budget_total"],
    "results_goal": [r"results_goal", r"result_goal", r"goal_results", r"target_results", r"target", r"goal"],
    "start_date": [r"start_date", r"campaign_start_date", r"flight_start", r"flight_start_date"],
    "end_date": [r"end_date", r"campaign_end_date", r"flight_end", r"flight_end_date"],
    "status": [r"status", r"campaign_status", r"delivery", r"delivery_status"],
    "artist": [r"artist", r"artist_name"],
}

# Columns that must never be auto-mapped to a field (they look similar).
FIELD_EXCLUDE = {
    "spend": re.compile(r"^cost_per_|^cost_pe|cpm|cpc|cpv"),
    "results": re.compile(r"^cost_per_|result_rate|results_goal|result_type|result_indicator|result_metric"),
    "clicks": re.compile(r"^cost_per_|ctr|click_through"),
    "impressions": re.compile(r"^cost_per_|cpm"),
}

RESULT_FAMILIES = {
    "landing_page_views": "Landing page views",
    "video_views": "Video views",
    "clicks": "Clicks",
    "engagements": "Engagements",
    "other": "Other results",
}

# Metric column that stands in for results when a file has no results column.
RESULT_SOURCE_COLUMN = {
    "video_views": "views",
    "clicks": "clicks",
    "engagements": "engagements",
}


def normalize_name(name: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


def result_family(text: object) -> str | None:
    """Map an objective / result label to a comparable result family."""
    if text is None:
        return None
    value = normalize_name(text)
    if not value or value in {"nan", "none"}:
        return None
    if "landing" in value or "lpv" in value:
        return "landing_page_views"
    if "video" in value or "thruplay" in value or "view" in value:
        return "video_views"
    if "engage" in value or "interaction" in value or "like" in value or "follow" in value:
        return "engagements"
    if "click" in value or "traffic" in value or "swipe" in value or "link" in value:
        return "clicks"
    return "other"


def canonical_platform(value: object) -> str:
    text = normalize_name(value)
    if any(key in text for key in ("meta", "facebook", "instagram", "fb", "ig")) and "google" not in text:
        return PLATFORM_META
    if "tiktok" in text or "tik_tok" in text:
        return PLATFORM_TIKTOK
    if "google" in text or "youtube" in text or text in {"yt", "gads", "dv360"}:
        return PLATFORM_GOOGLE
    if "snap" in text:
        return PLATFORM_SNAP
    if "wavo" in text:
        return PLATFORM_WAVO
    return PLATFORM_OTHER

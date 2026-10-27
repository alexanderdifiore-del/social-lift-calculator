"""Shared modeling constants aligned with the social lift calculator."""

ARTIST_TIER_MULTIPLIER = {
    "Emerging": 0.8,
    "Mid-tier": 1.4,
    "Established": 2.2,
    "Superstar": 3.5,
}

PLATFORM_MULTIPLIER = {
    "TikTok": 1.65,
    "Instagram Reels": 1.35,
    "YouTube Shorts": 1.45,
    "YouTube Video": 1.20,
    "YouTube Visualizer": 1.15,
    "YouTube Music Video": 1.30,
    "YouTube Live Performance": 1.25,
}

MARKET_MULTIPLIER = {
    "US": 1.25,
    "Global": 1.0,
    "Europe": 1.1,
    "LATAM": 1.2,
    "APAC": 1.15,
}

POST_TYPE_MULTIPLIER = {
    "Organic artist post": 1.15,
    "Influencer post": 1.35,
    "Paid boost": 1.25,
    "UGC trend": 1.6,
}

PAID_CHANNEL_DEFAULTS = {
    "TikTok Ads": {
        "platform_key": "TikTok",
        "default_cpm": 9.50,
        "default_ctr": 0.012,
        "view_to_stream_rate": 0.00018,
    },
    "Meta (Reels/Stories)": {
        "platform_key": "Instagram Reels",
        "default_cpm": 11.25,
        "default_ctr": 0.009,
        "view_to_stream_rate": 0.00012,
    },
    "YouTube Shorts Ads": {
        "platform_key": "YouTube Shorts",
        "default_cpm": 8.75,
        "default_ctr": 0.010,
        "view_to_stream_rate": 0.00014,
    },
    "YouTube In-Stream": {
        "platform_key": "YouTube Video",
        "default_cpm": 14.00,
        "default_ctr": 0.006,
        "view_to_stream_rate": 0.00010,
    },
}

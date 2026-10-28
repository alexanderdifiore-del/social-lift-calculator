"""Modeling constants from the original Lollie streaming-lift model.

These drive the optional Demo / Advanced Modeling simulation only. Production
reporting uses imported data.
"""

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
    "Snapchat": 1.20,
}

MARKET_MULTIPLIER = {
    "US": 1.25,
    "Global": 1.0,
    "Europe": 1.1,
    "LATAM": 1.2,
    "APAC": 1.15,
}

DSP_MULTIPLIER = {
    "All DSPs": 1.0,
    "Spotify-heavy": 1.15,
    "Apple-heavy": 1.05,
    "YouTube Music-heavy": 1.1,
    "Amazon-heavy": 0.95,
}

POST_TYPE_MULTIPLIER = {
    "Organic artist post": 1.15,
    "Influencer post": 1.35,
    "Paid boost": 1.25,
    "UGC trend": 1.6,
}

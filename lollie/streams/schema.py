"""Streaming export fields, aliases and the two kinds of streaming figures Lollie keeps apart."""

from __future__ import annotations

import re

from lollie.paid.schema import normalize_name

SCOPE_TOTAL = "total"
SCOPE_SOURCE = "source"
SCOPE_LABELS = {
    SCOPE_TOTAL: "Total track streams (all sources)",
    SCOPE_SOURCE: "Playlist / source-attributed streams",
}

DATE_FIELDS = ["date"]
TEXT_FIELDS = ["artist", "track_title", "isrc", "market", "dsp", "source_name"]
NUMERIC_FIELDS = ["streams"]
CANONICAL_FIELDS = DATE_FIELDS + TEXT_FIELDS + NUMERIC_FIELDS

REQUIRED_FIELDS = ["date", "streams"]

FIELD_LABELS = {
    "date": "Date (or date and time)",
    "artist": "Artist",
    "track_title": "Track title",
    "isrc": "ISRC",
    "market": "Country / market",
    "dsp": "DSP (streaming service)",
    "source_name": "Playlist / source name",
    "streams": "Streams",
}

FIELD_PATTERNS = {
    "date": [
        r"date", r"day", r"timestamp", r"datetime", r"date_time", r"stream_date", r"reporting_date",
        r"report_date", r"activity_date", r"time", r"hour",
    ],
    "artist": [r"artist", r"artist_name", r"primary_artist", r"main_artist"],
    "track_title": [
        r"track_title", r"track_name", r"track", r"song_title", r"song_name", r"song", r"title",
        r"recording_title", r"release_title",
    ],
    "isrc": [r"isrc", r"isrc_code", r"recording_isrc"],
    "market": [r"country", r"country_code", r"market", r"territory", r"region", r"country_name", r"geo"],
    "dsp": [r"dsp", r"service", r"platform", r"store", r"streaming_service", r"retailer", r"provider", r"source_platform"],
    "source_name": [
        r"playlist", r"playlist_name", r"source", r"stream_source", r"source_name", r"source_of_stream",
        r"playlist_source", r"context",
    ],
    "streams": [
        r"daily_streams", r"streams", r"stream_count", r"plays", r"total_streams", r"actual_streams",
        r"quantity", r"units", r"listens", r"stream",
    ],
}

# Values of a source column that mean "everything", not one playlist.
TOTAL_SOURCE_LABELS = {
    "", "all", "total", "all sources", "overall", "everything", "all streams", "total streams", "any",
}
TOTAL_DSP_LABELS = {"all", "total", "all dsps", "all services", "all platforms", "overall", "any"}


def dsp_label(value: object) -> str:
    """Tidy DSP names so 'spotify', 'Spotify Premium' style variants group together."""
    text = normalize_name(value)
    if not text or text == "nan":
        return "Unspecified"
    names = {
        "spotify": "Spotify",
        "apple": "Apple Music",
        "itunes": "Apple Music",
        "amazon": "Amazon Music",
        "deezer": "Deezer",
        "youtube": "YouTube Music",
        "tidal": "TIDAL",
        "pandora": "Pandora",
        "soundcloud": "SoundCloud",
        "tiktok": "TikTok / Resso",
    }
    for key, label in names.items():
        if key in text:
            return label
    return re.sub(r"\s+", " ", str(value).strip())

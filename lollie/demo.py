"""Clearly labelled SYNTHETIC demo data.

Nothing here comes from a real artist, report or company system. The numbers are
generated with a fixed random seed so the demo and the sample files are the same
every time. In the demo world some countries are given a modest streaming response
to the campaigns and others none, purely so the dashboard has something to show.

Run ``python -m lollie.demo sample_data`` to write sample CSV / Excel files you can
upload to practice with.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lollie.paid.ingest import Issue, IngestResult, combine_paid_frames, normalize_paid_frame, suggest_mapping
from lollie.paid.schema import PLATFORM_WAVO
from lollie.streams.ingest import (
    StreamIngestResult,
    combine_stream_frames,
    normalize_stream_frame,
    suggest_mapping as suggest_stream_mapping,
)
from lollie.streams.schema import SCOPE_TOTAL

DEMO_LABEL = "Synthetic demo data. These are not real campaigns, artists or streams."
DEMO_ARTIST = "Demo Artist (synthetic)"
TRACKS = [
    ("Neon Skyline", "QZDEM2600001", 1.0),
    ("Paper Moons", "QZDEM2600002", 0.6),
    ("Slow Motion Summer", "QZDEM2600003", 0.4),
]
PLAYLIST_NAME = "Demo Summer Playlist (synthetic)"
MARKET_BASE = {"United States": 5000, "United Kingdom": 1800, "Germany": 1500, "Brazil": 2600, "Mexico": 1200, "France": 900}
# Streaming response built into the synthetic world (share of baseline at full effect).
MARKET_RESPONSE = {"United States": 0.35, "United Kingdom": 0.18, "Germany": 0.04, "Brazil": 0.5, "Mexico": 0.0, "France": 0.0}
CPM = {"United States": 9.0, "United Kingdom": 8.0, "Germany": 8.0, "Brazil": 3.0, "Mexico": 2.5}
WEEKDAY = [0.95, 0.95, 0.97, 1.0, 1.08, 1.1, 1.0]

C1 = "DEMO | Neon Skyline | Single launch"
C1_START, C1_END = pd.Timestamp("2026-03-01"), pd.Timestamp("2026-03-21")
C2 = "DEMO | Summer Playlist push"
C2_START, C2_END = pd.Timestamp("2026-05-10"), pd.Timestamp("2026-05-30")
DATA_START, DATA_END = pd.Timestamp("2026-01-15"), pd.Timestamp("2026-06-30")

# (campaign, platform, market, budget, objective, result type, promoted item, isrc, start, end)
PLAN = [
    (C1, "Meta", "United States", 4200, "Landing Page Views", "Landing page views", "Neon Skyline", "QZDEM2600001", C1_START, C1_END),
    (C1, "Meta", "United Kingdom", 1600, "Landing Page Views", "Landing page views", "Neon Skyline", "QZDEM2600001", C1_START, C1_END),
    (C1, "Meta", "Germany", 1000, "Landing Page Views", "Landing page views", "Neon Skyline", "QZDEM2600001", C1_START, C1_END),
    (C1, "Meta", "Brazil", 1400, "Landing Page Views", "Landing page views", "Neon Skyline", "QZDEM2600001", C1_START, C1_END),
    (C1, "Meta", "Mexico", 800, "Landing Page Views", "Landing page views", "Neon Skyline", "QZDEM2600001", C1_START, C1_END),
    (C1, "TikTok", "United States", 1800, "Video Views", "Video views", "Neon Skyline", "QZDEM2600001", C1_START, C1_END),
    (C1, "TikTok", "Brazil", 1200, "Video Views", "Video views", "Neon Skyline", "QZDEM2600001", C1_START, C1_END),
    (C2, "Meta", "United States", 3000, "Landing Page Views", "Landing page views", PLAYLIST_NAME, "", C2_START, C2_END),
    (C2, "Meta", "Brazil", 1800, "Landing Page Views", "Landing page views", PLAYLIST_NAME, "", C2_START, C2_END),
]


def _paid_rows() -> pd.DataFrame:
    rng = np.random.default_rng(2026)
    rows = []
    for campaign, platform, market, budget, objective, result_type, item, isrc, start, end in PLAN:
        days = pd.date_range(start, end)
        weights = rng.uniform(0.85, 1.15, len(days))
        spend = budget * weights / weights.sum()
        target_cpr = 0.35 if result_type == "Landing page views" else 0.03
        goal = round(budget / target_cpr * 1.05)
        for day, amount in zip(days, spend):
            impressions = amount / CPM[market] * 1000
            clicks = impressions * rng.uniform(0.009, 0.015)
            lpv = clicks * rng.uniform(0.5, 0.65)
            views = impressions * rng.uniform(0.2, 0.32)
            results = lpv if result_type == "Landing page views" else views
            rows.append(
                {
                    "Campaign ID": f"{'C1' if campaign == C1 else 'C2'}-{platform[:2].upper()}-{market[:2].upper()}",
                    "Campaign Name": campaign,
                    "Artist": DEMO_ARTIST,
                    "Promoted Content": item,
                    "ISRC": isrc,
                    "Reporting Date": day.strftime("%Y-%m-%d"),
                    "Country": market,
                    "Platform": platform,
                    "Campaign Start": start.strftime("%Y-%m-%d"),
                    "Campaign End": end.strftime("%Y-%m-%d"),
                    "Objective": objective,
                    "Result Type": result_type,
                    "Results": round(results),
                    "Results Goal": goal,
                    "Budget": budget,
                    "Spend (USD)": round(amount, 2),
                    "Impressions": round(impressions),
                    "Video Views": round(views),
                    "Engagements": round(impressions * rng.uniform(0.02, 0.04)),
                    "Clicks": round(clicks),
                    "Landing Page Views": round(lpv),
                }
            )
    return pd.DataFrame(rows)


def demo_paid_raw() -> pd.DataFrame:
    """A WAVO-style consolidated advertising report (synthetic)."""
    return _paid_rows()


def _response(day: pd.Timestamp, start: pd.Timestamp, end: pd.Timestamp, gain: float) -> float:
    if day < start:
        return 0.0
    if day <= end:
        return gain * min(1.0, ((day - start).days + 1) / 4)
    return gain * float(np.exp(-((day - end).days) / 5))


def demo_streams_raw() -> pd.DataFrame:
    """A streaming export with daily rows per track, country and service (synthetic)."""
    rng = np.random.default_rng(7)
    days = pd.date_range(DATA_START, DATA_END)
    rows = []
    for market, base in MARKET_BASE.items():
        gain = MARKET_RESPONSE[market]
        for title, isrc, track_share in TRACKS:
            for dsp, dsp_share in (("Spotify", 0.75), ("Apple Music", 0.25)):
                level = base * track_share * dsp_share
                for day in days:
                    if market == "Germany" and pd.Timestamp("2026-03-08") <= day <= pd.Timestamp("2026-03-11"):
                        continue
                    lift = 0.0
                    if title == "Neon Skyline":
                        lift += _response(day, C1_START, C1_END, gain)
                    if market in ("United States", "Brazil"):
                        lift += _response(day, C2_START, C2_END, gain * 0.6)
                    value = level * WEEKDAY[day.day_of_week] * (1 + lift) * rng.lognormal(0, 0.06)
                    rows.append(
                        {
                            "Date": day.strftime("%Y-%m-%d"),
                            "Artist": DEMO_ARTIST,
                            "Track Title": title,
                            "ISRC": isrc,
                            "Country": market,
                            "DSP": dsp,
                            "Playlist / Source": "Total",
                            "Streams": int(round(value)),
                        }
                    )
    frame = pd.DataFrame(rows)
    editorial = frame[(frame["Track Title"] == "Neon Skyline") & (frame["DSP"] == "Spotify") & (frame["Country"] == "United States")].copy()
    editorial["Playlist / Source"] = "Demo Editorial Playlist (synthetic)"
    editorial["Streams"] = (editorial["Streams"] * 0.12).round().astype(int)
    return pd.concat([frame, editorial], ignore_index=True)


def demo_track_list_raw() -> pd.DataFrame:
    """A track list for the demo playlist campaign (synthetic)."""
    return pd.DataFrame(
        {
            "Track Title": [t[0] for t in TRACKS],
            "Artist": DEMO_ARTIST,
            "ISRC": [t[1] for t in TRACKS],
            "Added to playlist": ["2026-05-01"] * len(TRACKS),
            "Removed from playlist": [""] * len(TRACKS),
        }
    )


def load_demo() -> tuple[pd.DataFrame, pd.DataFrame, list[Issue]]:
    """Synthetic data passed through the same importers real files use."""
    raw_paid = demo_paid_raw()
    paid = normalize_paid_frame(
        raw_paid, suggest_mapping(list(raw_paid.columns)), PLATFORM_WAVO, source_label="synthetic WAVO-style report"
    )
    paid_frame, paid_issues = combine_paid_frames([_with_hash(paid, "demo-paid")])

    raw_streams = demo_streams_raw()
    streams = normalize_stream_frame(
        raw_streams, suggest_stream_mapping(list(raw_streams.columns)), default_scope=SCOPE_TOTAL,
        source_label="synthetic streaming export",
    )
    streams.file_hash = "demo-streams"
    stream_frame, stream_issues = combine_stream_frames([streams])
    return paid_frame, stream_frame, paid_issues + stream_issues


def _with_hash(result: IngestResult | StreamIngestResult, digest: str):
    result.file_hash = digest
    return result


def write_sample_files(folder: str | Path) -> list[Path]:
    """Write synthetic sample files to practise uploading."""
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    paid_path = out / "sample_wavo_paid_media.csv"
    streams_csv = out / "sample_streaming_daily.csv"
    streams_xlsx = out / "sample_streaming_daily.xlsx"
    tracks_path = out / "sample_playlist_track_list.csv"
    demo_paid_raw().to_csv(paid_path, index=False)
    streams = demo_streams_raw()
    streams.to_csv(streams_csv, index=False)
    streams.to_excel(streams_xlsx, index=False)
    demo_track_list_raw().to_csv(tracks_path, index=False)
    return [paid_path, streams_csv, streams_xlsx, tracks_path]


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sample_data"
    for path in write_sample_files(target):
        print(f"wrote {path}")

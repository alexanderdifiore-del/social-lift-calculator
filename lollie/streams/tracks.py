"""Which tracks a campaign promoted, and how streaming rows are tied to them.

A campaign can promote one song, a playlist / several songs, or an artist's whole
catalog. Lollie never reads a playlist from Spotify: track membership comes from
a list the user confirms. A playlist link is stored only as a reference.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from lollie.paid.ingest import Issue
from lollie.streams.ingest import clean_isrc, clean_title, make_track_key
from lollie.streams.schema import SCOPE_TOTAL

MODE_SINGLE = "single"
MODE_PLAYLIST = "playlist"
MODE_CATALOG = "catalog"
MODE_LABELS = {
    MODE_SINGLE: "A single song",
    MODE_PLAYLIST: "A playlist or several songs",
    MODE_CATALOG: "The artist's catalog",
}

TRACK_COLUMNS = ["title", "artist", "isrc", "track_key", "member_from", "member_to"]
TRACK_LIST_PATTERNS = {
    "title": [r"track_title", r"track_name", r"track", r"song", r"song_title", r"title", r"name"],
    "artist": [r"artist", r"artist_name"],
    "isrc": [r"isrc", r"isrc_code"],
    "member_from": [r"added", r"added_date", r"member_from", r"start", r"start_date", r"in_playlist_from"],
    "member_to": [r"removed", r"removed_date", r"member_to", r"end", r"end_date", r"in_playlist_to"],
}

SPOTIFY_PLAYLIST_URL = re.compile(r"open\.spotify\.com/(?:intl-[a-z]+/)?playlist/([A-Za-z0-9]+)")


@dataclass
class CampaignScope:
    """The songs a campaign is analysed against."""

    mode: str = MODE_SINGLE
    tracks: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=TRACK_COLUMNS))
    playlist_name: str = ""
    playlist_url: str = ""
    membership_verified: bool = False
    catalog_confirmed: bool = False

    @property
    def track_keys(self) -> list[str]:
        return self.tracks["track_key"].tolist() if not self.tracks.empty else []

    @property
    def track_count(self) -> int:
        return len(self.tracks)

    @property
    def label(self) -> str:
        if self.mode == MODE_SINGLE and self.track_count == 1:
            return str(self.tracks.iloc[0]["title"])
        if self.mode == MODE_PLAYLIST:
            name = self.playlist_name.strip() or "Playlist"
            return f"{name} ({self.track_count} tracks)"
        if self.mode == MODE_CATALOG:
            return f"Artist catalog ({self.track_count} tracks)"
        return "No track selected"

    @property
    def has_membership_dates(self) -> bool:
        return bool(self.tracks[["member_from", "member_to"]].notna().any().any()) if not self.tracks.empty else False


def parse_playlist_url(url: str) -> str | None:
    """Spotify playlist ID from a link, kept only as a reference."""
    match = SPOTIFY_PLAYLIST_URL.search(url or "")
    return match.group(1) if match else None


def tracks_from_stream_frame(stream_frame: pd.DataFrame) -> pd.DataFrame:
    """Every distinct track found in the streaming data (total-stream rows first)."""
    if stream_frame.empty:
        return pd.DataFrame(columns=TRACK_COLUMNS)
    tracks = (
        stream_frame.sort_values("scope", ascending=False)
        .groupby("track_key", as_index=False)
        .agg(title=("track_title", "first"), artist=("artist", "first"), isrc=("isrc", "first"))
    )
    tracks["member_from"] = pd.NaT
    tracks["member_to"] = pd.NaT
    return tracks[TRACK_COLUMNS].sort_values(["artist", "title"]).reset_index(drop=True)


def build_track_table(entries: pd.DataFrame) -> pd.DataFrame:
    """Normalise a track list (title / artist / ISRC / optional dates) and drop repeats."""
    frame = pd.DataFrame(index=entries.index)
    frame["title"] = entries["title"].astype("string").fillna("").str.strip() if "title" in entries else ""
    frame["artist"] = entries["artist"].astype("string").fillna("").str.strip() if "artist" in entries else ""
    frame["isrc"] = entries["isrc"].map(clean_isrc) if "isrc" in entries else None
    for name in ("member_from", "member_to"):
        frame[name] = pd.to_datetime(entries[name], errors="coerce") if name in entries else pd.NaT
    frame = frame[(frame["title"] != "") | frame["isrc"].notna()].copy()
    frame["track_key"] = [make_track_key(i, t, a) for i, t, a in zip(frame["isrc"], frame["title"], frame["artist"])]
    frame = frame.drop_duplicates("track_key", keep="first")
    return frame[TRACK_COLUMNS].reset_index(drop=True)


def track_list_mapping(columns: list[str]) -> dict[str, str | None]:
    mapping: dict[str, str | None] = {}
    used: set[str] = set()
    normalized = {c: re.sub(r"[^a-z0-9]+", "_", str(c).lower()).strip("_") for c in columns}
    for name, patterns in TRACK_LIST_PATTERNS.items():
        mapping[name] = None
        for pattern in patterns:
            hit = next((c for c, n in normalized.items() if c not in used and re.fullmatch(pattern, n)), None)
            if hit:
                mapping[name] = hit
                used.add(hit)
                break
    return mapping


def load_track_list(raw: pd.DataFrame, mapping: dict[str, str | None] | None = None) -> tuple[pd.DataFrame, list[Issue]]:
    """Turn an uploaded track list (CSV / Excel) into the track table."""
    issues: list[Issue] = []
    mapping = mapping or track_list_mapping(list(raw.columns))
    entries = pd.DataFrame({name: raw[col] for name, col in mapping.items() if col and col in raw.columns})
    if "title" not in entries and "isrc" not in entries:
        issues.append(Issue("error", "The track list needs a track title or ISRC column."))
        return pd.DataFrame(columns=TRACK_COLUMNS), issues
    table = build_track_table(entries)
    skipped = len(raw) - len(table)
    if skipped > 0:
        issues.append(Issue("info", f"{skipped} track list row(s) were blank or repeated and were skipped."))
    if table["isrc"].isna().all():
        issues.append(Issue("info", "No ISRCs in the track list; tracks are matched to streaming rows by title and artist, which is less reliable."))
    return table, issues


def match_streams(stream_frame: pd.DataFrame, tracks: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach each stream row to a listed track.

    Order of matching: ISRC, then title (+ artist when both sides have one).
    Returns (matched stream rows with the listed track's key, coverage table).
    """
    columns = ["Track", "Artist", "ISRC", "Matched by", "Days with streams", "Total streams"]
    if stream_frame.empty or tracks.empty:
        return stream_frame.iloc[0:0].copy(), pd.DataFrame(columns=columns)

    by_isrc = {row.isrc: row.track_key for row in tracks.itertuples() if isinstance(row.isrc, str) and row.isrc}
    by_title: dict[str, list[tuple[str, str]]] = {}
    for row in tracks.itertuples():
        by_title.setdefault(clean_title(row.title), []).append((clean_title(row.artist), row.track_key))

    rows = stream_frame[["track_key", "track_title", "artist", "isrc"]].drop_duplicates("track_key")
    mapping: dict[str, tuple[str, str]] = {}
    for row in rows.itertuples():
        code = clean_isrc(row.isrc)
        if code and code in by_isrc:
            mapping[row.track_key] = (by_isrc[code], "ISRC")
            continue
        candidates = by_title.get(clean_title(row.track_title), [])
        artist = clean_title(row.artist)
        exact = [key for (a, key) in candidates if a and artist and a == artist]
        loose = [key for (a, key) in candidates if not a or not artist]
        pick = exact or loose
        if len(pick) == 1:
            mapping[row.track_key] = (pick[0], "Title" + (" and artist" if exact else ""))

    matched = stream_frame[stream_frame["track_key"].isin(mapping)].copy()
    matched["listed_track_key"] = matched["track_key"].map(lambda key: mapping[key][0])
    matched["matched_by"] = matched["track_key"].map(lambda key: mapping[key][1])
    matched["track_key"] = matched["listed_track_key"]
    matched = matched.drop(columns=["listed_track_key"])
    matched = _within_membership(matched, tracks)
    same_day = ["date", "market_code", "dsp", "source_name", "scope", "track_key"]
    repeats = matched.duplicated(same_day, keep=False)
    collapsed = 0
    if repeats.any():
        # The same listed track arrived under two identities (e.g. with and without an ISRC).
        keep = matched.groupby(same_day)["streams"].idxmax()
        collapsed = int(len(matched) - len(keep))
        matched = matched.loc[keep.values].sort_values(["date", "market_code"])
    matched.attrs["collapsed_rows"] = collapsed

    coverage_rows = []
    total_rows = matched[matched["scope"] == SCOPE_TOTAL]
    for row in tracks.itertuples():
        mine = total_rows[total_rows["track_key"] == row.track_key]
        how = mine["matched_by"].iloc[0] if not mine.empty else "Not found in streaming data"
        coverage_rows.append(
            {
                "Track": row.title,
                "Artist": row.artist,
                "ISRC": row.isrc if isinstance(row.isrc, str) else "",
                "Matched by": how,
                "Days with streams": int(mine["date"].nunique()) if not mine.empty else 0,
                "Total streams": float(mine["streams"].sum()) if not mine.empty else 0.0,
            }
        )
    return matched, pd.DataFrame(coverage_rows, columns=columns)


def _within_membership(matched: pd.DataFrame, tracks: pd.DataFrame) -> pd.DataFrame:
    """Keep a track's days only while the user said it was in the playlist / on the campaign."""
    if matched.empty or not tracks[["member_from", "member_to"]].notna().any().any():
        return matched
    bounds = tracks.set_index("track_key")[["member_from", "member_to"]]
    start = matched["track_key"].map(bounds["member_from"])
    end = matched["track_key"].map(bounds["member_to"])
    keep = (start.isna() | (matched["date"] >= start)) & (end.isna() | (matched["date"] <= end))
    return matched.loc[keep]


def daily_scope_totals(matched: pd.DataFrame, dsp: str | None = None, market_codes: list[str] | None = None) -> pd.DataFrame:
    """Total track streams by day and market, each track counted once.

    Only total-stream rows are used. Playlist / source-attributed rows are never
    added in, because they are a slice of the same streams.
    """
    columns = ["date", "market_code", "market", "streams", "tracks_reporting"]
    if matched.empty:
        return pd.DataFrame(columns=columns)
    frame = matched[matched["scope"] == SCOPE_TOTAL]
    if dsp and dsp != "All DSPs":
        frame = frame[frame["dsp"] == dsp]
    if market_codes is not None:
        frame = frame[frame["market_code"].isin(market_codes)]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    daily = (
        frame.groupby(["date", "market_code", "market"], as_index=False)
        .agg(streams=("streams", "sum"), tracks_reporting=("track_key", "nunique"))
        .sort_values(["market_code", "date"])
    )
    return daily[columns].reset_index(drop=True)


def track_level_daily(matched: pd.DataFrame, dsp: str | None = None, market_codes: list[str] | None = None) -> pd.DataFrame:
    """Song-level daily total streams (kept so one track is never hidden by a playlist total)."""
    columns = ["date", "track_key", "track_title", "streams"]
    if matched.empty:
        return pd.DataFrame(columns=columns)
    frame = matched[matched["scope"] == SCOPE_TOTAL]
    if dsp and dsp != "All DSPs":
        frame = frame[frame["dsp"] == dsp]
    if market_codes is not None:
        frame = frame[frame["market_code"].isin(market_codes)]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    return frame.groupby(["date", "track_key", "track_title"], as_index=False)["streams"].sum()[columns]


def source_attributed_totals(matched: pd.DataFrame) -> pd.DataFrame:
    """Playlist / source-attributed streams, shown as their own table."""
    frame = matched[matched["scope"] != SCOPE_TOTAL] if not matched.empty else matched
    if frame.empty:
        return pd.DataFrame(columns=["Source", "Streams", "Days"])
    out = frame.groupby("source_name").agg(Streams=("streams", "sum"), Days=("date", "nunique")).reset_index()
    return out.rename(columns={"source_name": "Source"}).sort_values("Streams", ascending=False).reset_index(drop=True)

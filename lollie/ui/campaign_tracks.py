"""Section A control: which song, playlist or catalog a campaign promoted."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from lollie.streams.ingest import clean_isrc, clean_title
from lollie.streams.tracks import (
    MODE_LABELS,
    MODE_PLAYLIST,
    MODE_SINGLE,
    TRACK_COLUMNS,
    CampaignScope,
    parse_playlist_url,
)
from lollie.ui.stream_import import read_track_list


def _label(row) -> str:
    artist = f" - {row['artist']}" if row["artist"] else ""
    code = f" ({row['isrc']})" if isinstance(row["isrc"], str) and row["isrc"] else ""
    return f"{row['title']}{artist}{code}"


def promoted_hints(campaign_rows: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Promoted item names and ISRCs written in the advertising report for this campaign."""
    if campaign_rows.empty:
        return [], []
    items = [str(v) for v in campaign_rows["promoted_item"].dropna().unique()]
    codes = [c for c in (clean_isrc(v) for v in campaign_rows["isrc"].dropna().unique()) if c]
    return items, codes


def _default_single(tracks: pd.DataFrame, items: list[str], codes: list[str]) -> int:
    for position, row in enumerate(tracks.itertuples()):
        if isinstance(row.isrc, str) and row.isrc in codes:
            return position
    wanted = {clean_title(i) for i in items}
    for position, row in enumerate(tracks.itertuples()):
        if clean_title(row.title) in wanted:
            return position
    return 0


def choose_campaign_scope(
    stream_tracks: pd.DataFrame,
    campaign_rows: pd.DataFrame,
    track_file,
    *,
    key: str,
    container,
) -> tuple[CampaignScope, list]:
    """Let the user say what the campaign promoted. Returns the scope and any import notes."""
    notes: list = []
    items, codes = promoted_hints(campaign_rows)
    scope = CampaignScope()
    with container:
        if stream_tracks.empty and track_file is None:
            st.info("Upload a streaming report to choose the promoted song or playlist.")
            return scope, notes

        playlist_hint = next((i for i in items if "playlist" in i.lower()), "")
        default_mode = MODE_PLAYLIST if playlist_hint or len(items) > 1 else MODE_SINGLE
        modes = list(MODE_LABELS)
        mode = st.radio(
            "What was promoted?",
            modes,
            index=modes.index(default_mode),
            format_func=lambda value: MODE_LABELS[value],
            horizontal=True,
            key=f"{key}_mode",
        )
        scope.mode = mode
        if items:
            st.caption("Promoted in the advertising report: " + ", ".join(items[:4]))

        if mode == MODE_SINGLE:
            if stream_tracks.empty:
                st.info("No tracks were found in the streaming data.")
                return scope, notes
            options = list(range(len(stream_tracks)))
            choice = st.selectbox(
                "Promoted song",
                options,
                index=_default_single(stream_tracks, items, codes),
                format_func=lambda i: _label(stream_tracks.iloc[i]),
                key=f"{key}_single",
            )
            scope.tracks = stream_tracks.iloc[[choice]].reset_index(drop=True)

        elif mode == MODE_PLAYLIST:
            cols = st.columns(2)
            scope.playlist_name = cols[0].text_input(
                "Playlist name (optional)", value=playlist_hint, key=f"{key}_playlist_name"
            )
            scope.playlist_url = cols[1].text_input(
                "Spotify playlist link (optional, reference only)", key=f"{key}_playlist_url",
                help="Lollie does not read playlists from Spotify. The link is only noted in the summary.",
            )
            if scope.playlist_url and parse_playlist_url(scope.playlist_url) is None:
                st.caption("That does not look like a Spotify playlist link. It is kept as a note only.")
            if track_file is not None:
                table, issues = read_track_list(track_file, st.container())
                notes.extend(issues)
                scope.tracks = table
                st.caption(f"Using the uploaded track list: {len(table)} track(s).")
            else:
                options = list(range(len(stream_tracks)))
                chosen = st.multiselect(
                    "Tracks on the playlist or in the campaign",
                    options,
                    format_func=lambda i: _label(stream_tracks.iloc[i]),
                    key=f"{key}_multi",
                    help="Choose the tracks, or upload a track list in the sidebar (Track list). Track membership has to come "
                    "from you; Lollie cannot see a playlist's history.",
                )
                scope.tracks = stream_tracks.iloc[chosen].reset_index(drop=True) if chosen else pd.DataFrame(columns=TRACK_COLUMNS)
            scope.membership_verified = st.checkbox(
                "I have confirmed these tracks were on the playlist during the campaign period.",
                key=f"{key}_verified",
            )
            if not scope.membership_verified and not scope.tracks.empty:
                st.caption("Track membership is not marked as verified; the summary will say so.")

        else:
            scope.tracks = stream_tracks
            scope.catalog_confirmed = st.checkbox(
                f"The streaming file covers the artist's whole catalog ({len(stream_tracks)} tracks found).",
                key=f"{key}_catalog",
                help="Catalog totals are only meaningful when the file includes every track.",
            )
            scope.membership_verified = scope.catalog_confirmed
            if not scope.catalog_confirmed:
                st.info("Confirm the file covers the whole catalog to analyse it as one group.")
                scope.tracks = pd.DataFrame(columns=TRACK_COLUMNS)
    return scope, notes

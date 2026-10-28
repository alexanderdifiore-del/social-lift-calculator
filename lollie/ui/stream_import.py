"""Upload and column matching for streaming reports (Opus or other approved CSV / Excel exports)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from lollie.imports.file_loader import load_tabular_upload, read_raw_bytes
from lollie.paid.ingest import Issue, file_fingerprint
from lollie.streams.ingest import (
    STREAM_HEADER_HINTS,
    StreamIngestResult,
    combine_stream_frames,
    normalize_stream_frame,
    suggest_mapping,
)
from lollie.streams.schema import CANONICAL_FIELDS, FIELD_LABELS, SCOPE_LABELS, SCOPE_SOURCE, SCOPE_TOTAL
from lollie.streams.tracks import TRACK_COLUMNS, load_track_list, track_list_mapping

UPLOAD_TYPES = ["csv", "xlsx", "xls"]


@dataclass
class StreamData:
    frame: pd.DataFrame = field(default_factory=pd.DataFrame)
    issues: list[Issue] = field(default_factory=list)
    results: list[StreamIngestResult] = field(default_factory=list)
    is_demo: bool = False

    @property
    def is_empty(self) -> bool:
        return self.frame.empty


def ingest_stream_files(files: list, container) -> StreamData:
    """Read, match columns and validate uploaded streaming reports."""
    results: list[StreamIngestResult] = []
    with container:
        for index, uploaded in enumerate(files):
            digest = file_fingerprint(read_raw_bytes(uploaded))
            key = f"stream_{digest[:10]}_{index}"
            with st.expander(f"Import settings: {uploaded.name}", expanded=False):
                try:
                    raw = load_tabular_upload(uploaded, header_hints=STREAM_HEADER_HINTS)
                except Exception as error:  # noqa: BLE001 - shown to the user
                    st.error(f"'{uploaded.name}' could not be read: {error}")
                    continue
                if raw.empty:
                    st.error(f"'{uploaded.name}' has no rows.")
                    continue
                columns = list(raw.columns)
                suggested = suggest_mapping(columns)
                st.caption(
                    "Match each Lollie field to a column in your file. Only Date and Streams are required. "
                    "Leave a field blank when the file does not have it."
                )
                options = ["(not in file)"] + columns
                mapping: dict[str, str | None] = {}
                grid = st.columns(3)
                for position, name in enumerate(CANONICAL_FIELDS):
                    default = suggested.get(name)
                    choice = grid[position % 3].selectbox(
                        FIELD_LABELS.get(name, name),
                        options,
                        index=options.index(default) if default in options else 0,
                        key=f"{key}_field_{name}",
                    )
                    mapping[name] = None if choice == "(not in file)" else choice

                scope = st.radio(
                    "What do the streams in this file represent?",
                    [SCOPE_TOTAL, SCOPE_SOURCE],
                    format_func=lambda value: SCOPE_LABELS[value],
                    key=f"{key}_scope",
                    help="Total track streams are used for the analysis. Streams credited to one playlist or source are a "
                    "slice of those streams and are kept separate so nothing is counted twice.",
                )
                artist = track = dsp = ""
                needs_track = mapping.get("track_title") is None and mapping.get("isrc") is None
                if mapping.get("artist") is None or needs_track or mapping.get("dsp") is None:
                    st.caption("For fields your file does not have, you can type one value that applies to every row.")
                    cols = st.columns(3)
                    if mapping.get("artist") is None:
                        artist = cols[0].text_input("Artist for every row", key=f"{key}_artist")
                    if needs_track:
                        track = cols[1].text_input("Track title for every row", key=f"{key}_track")
                    if mapping.get("dsp") is None:
                        dsp = cols[2].text_input("DSP for every row", key=f"{key}_dsp", placeholder="e.g. Spotify")
                st.dataframe(raw.head(8), width="stretch")

            result = normalize_stream_frame(
                raw, mapping, default_scope=scope, default_artist=artist, default_track=track, default_dsp=dsp,
                source_label=uploaded.name,
            )
            result.file_hash = digest
            results.append(result)
            st.caption(f"{uploaded.name}: {len(result.frame):,} daily rows read.")
            for issue in result.issues:
                if issue.level == "error":
                    st.error(f"{uploaded.name}: {issue.message}")
                elif issue.level == "warning":
                    st.warning(f"{uploaded.name}: {issue.message}")
    frame, combine_issues = combine_stream_frames(results)
    info = [i for r in results for i in r.issues if i.level == "info"]
    return StreamData(frame=frame, issues=info + combine_issues, results=results)


def read_track_list(uploaded, container) -> tuple[pd.DataFrame, list[Issue]]:
    """Load an uploaded list of the tracks on a playlist or campaign."""
    with container:
        try:
            raw = load_tabular_upload(uploaded, header_hints=("track", "title", "song", "isrc", "artist"))
        except Exception as error:  # noqa: BLE001 - shown to the user
            st.error(f"The track list could not be read: {error}")
            return pd.DataFrame(columns=TRACK_COLUMNS), []
    table, issues = load_track_list(raw, track_list_mapping(list(raw.columns)))
    return table, issues

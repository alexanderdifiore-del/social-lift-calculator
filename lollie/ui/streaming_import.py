"""Streaming CSV / Excel upload with column mapping (original Lollie workflow)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from lollie.imports.file_loader import guess_column, load_tabular_upload
from lollie.streaming import StreamingPrep, prepare_streaming_frame

STREAM_HEADER_HINTS = ("timestamp", "date", "time", "streams", "actual", "plays")


def render_streaming_import(
    uploaded,
    container,
    *,
    post_timestamp: datetime,
    impact_window_hours: int,
) -> StreamingPrep | None:
    """Read the uploaded file, let the user confirm the mapping, return the prepared frame."""
    with container:
        try:
            raw = load_tabular_upload(uploaded, header_hints=STREAM_HEADER_HINTS)
        except Exception as error:  # noqa: BLE001 - shown to the user
            st.error(f"The uploaded streaming file could not be read: {error}")
            return None
        raw = raw.loc[:, [not str(col).lower().startswith("unnamed") for col in raw.columns]]
        columns = list(raw.columns)
        if len(columns) < 2:
            st.error(
                "The file was uploaded, but lollie only detected one usable column. Make sure the first real row "
                "contains: timestamp, actual_streams (and optionally expected_baseline_streams)."
            )
            return None

        def index_of(guess: str | None, fallback: int) -> int:
            if guess in columns:
                return columns.index(guess)
            return min(fallback, len(columns) - 1)

        timestamp_guess = guess_column(columns, ["timestamp", "date", "time", "day"])
        actual_guess = guess_column(columns, ["actual_streams", "actual", "streams", "plays"])
        baseline_guess = guess_column(columns, ["expected", "baseline"])
        market_guess = guess_column(columns, ["market", "country", "territory"])

        st.success("File uploaded. Confirm the column mapping below.")
        with st.expander("Streaming file: preview and column mapping", expanded=False):
            st.dataframe(raw.head(10), width="stretch")
            timestamp_column = st.selectbox("Select timestamp column", columns, index=index_of(timestamp_guess, 0))
            actual_column = st.selectbox("Select actual streams column", columns, index=index_of(actual_guess, 1))
            baseline_options = ["Auto-estimate baseline"] + columns
            baseline_column = st.selectbox(
                "Select expected baseline column",
                baseline_options,
                index=baseline_options.index(baseline_guess) if baseline_guess in baseline_options else 0,
            )
            market_options = ["(none)"] + columns
            market_column = st.selectbox(
                "Select market column (optional)",
                market_options,
                index=market_options.index(market_guess) if market_guess in market_options else 0,
                help="Only needed if the file contains several markets and you want to analyze one at a time.",
            )
            market = None
            if market_column != "(none)":
                values = sorted(raw[market_column].dropna().astype(str).str.strip().unique().tolist())
                market = st.selectbox("Market to analyze", ["All markets"] + values)

        prep = prepare_streaming_frame(
            raw,
            timestamp_column,
            actual_column,
            None if baseline_column == "Auto-estimate baseline" else baseline_column,
            post_timestamp=post_timestamp,
            impact_window_hours=impact_window_hours,
            market_column=None if market_column == "(none)" else market_column,
            market=market,
        )
        if prep.error:
            st.error(prep.error)
            return None
        return prep

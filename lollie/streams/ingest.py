"""Read, map and validate streaming exports (CSV / Excel).

Nothing here invents data: missing days stay missing, hourly rows are only rolled
up to a day when all 24 hours are present, and roll-up rows ("All countries",
"All services") are never added on top of the detail rows they summarise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from lollie.geo import ALL_MARKETS_CODE, ALL_MARKETS_LABEL, normalize_market
from lollie.paid.ingest import Issue, _clean_numeric, file_fingerprint
from lollie.paid.schema import normalize_name
from lollie.streams.schema import (
    CANONICAL_FIELDS,
    FIELD_PATTERNS,
    NUMERIC_FIELDS,
    REQUIRED_FIELDS,
    SCOPE_SOURCE,
    SCOPE_TOTAL,
    TEXT_FIELDS,
    TOTAL_DSP_LABELS,
    TOTAL_SOURCE_LABELS,
    dsp_label,
)

OUTPUT_COLUMNS = [
    "date", "artist", "track_title", "isrc", "track_key", "market", "market_code", "dsp",
    "source_name", "scope", "streams", "granularity", "source_file",
]
ALL_DSPS_LABEL = "All DSPs"
STREAM_HEADER_HINTS = ("date", "day", "timestamp", "streams", "plays", "track", "isrc", "country", "stream")


@dataclass
class StreamIngestResult:
    frame: pd.DataFrame
    issues: list[Issue] = field(default_factory=list)
    source_label: str = ""
    file_hash: str = ""

    @property
    def has_errors(self) -> bool:
        return any(i.level == "error" for i in self.issues)


def suggest_mapping(columns: list[str]) -> dict[str, str | None]:
    """Suggest a file column for each streaming field. A column is never used twice."""
    normalized = {col: normalize_name(col) for col in columns}
    mapping: dict[str, str | None] = {name: None for name in CANONICAL_FIELDS}
    used: set[str] = set()
    for name in CANONICAL_FIELDS:
        for pattern in FIELD_PATTERNS.get(name, []):
            regex = re.compile(pattern)
            for col, norm in normalized.items():
                if col not in used and regex.fullmatch(norm):
                    mapping[name] = col
                    used.add(col)
                    break
            if mapping[name] is not None:
                break
    return mapping


def clean_isrc(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = re.sub(r"[^A-Za-z0-9]", "", str(value)).upper()
    return text if len(text) == 12 else (text or None)


def clean_title(value: object) -> str:
    """Lower-case, punctuation-free title used only for matching."""
    text = str(value or "").lower()
    text = re.sub(r"\(.*?(feat|ft|with).*?\)|\[.*?\]", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def make_track_key(isrc: object, title: object, artist: object) -> str:
    code = clean_isrc(isrc)
    if code:
        return f"ISRC:{code}"
    return f"TITLE:{clean_title(title)}|{clean_title(artist)}"


def _parse_dates(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.replace("\n", " ").str.strip()
    parsed = pd.to_datetime(text, errors="coerce", format="mixed")
    if parsed.dt.tz is not None:
        parsed = parsed.dt.tz_localize(None)
    return parsed


def normalize_stream_frame(
    raw: pd.DataFrame,
    mapping: dict[str, str | None],
    *,
    default_scope: str = SCOPE_TOTAL,
    default_artist: str = "",
    default_track: str = "",
    default_dsp: str = "",
    source_label: str = "",
) -> StreamIngestResult:
    """Convert a raw streaming export into Lollie's streaming table (one row per day)."""
    issues: list[Issue] = []

    def column(name: str) -> pd.Series | None:
        col = mapping.get(name)
        return raw[col] if col and col in raw.columns else None

    out = pd.DataFrame(index=raw.index)

    date_series = column("date")
    out["date"] = _parse_dates(date_series) if date_series is not None else pd.NaT
    streams = column("streams")
    if streams is None:
        out["streams"] = np.nan
    else:
        numbers, bad = _clean_numeric(streams)
        out["streams"] = numbers
        if bad:
            issues.append(Issue("warning", f"{bad} value(s) in '{mapping['streams']}' were not numbers and were left blank."))

    for name in TEXT_FIELDS:
        series = column(name)
        if series is None:
            out[name] = None
        else:
            text = series.astype("string").str.strip()
            text = text.mask(text.isin(["", "nan", "None", "<NA>"]))
            out[name] = text.astype(object).where(text.notna(), None)

    for name in REQUIRED_FIELDS:
        if column(name) is None:
            label = "date" if name == "date" else "streams"
            issues.append(Issue("error", f"No {label} column was matched. A {label} column is required."))
    if any(i.level == "error" for i in issues):
        return StreamIngestResult(pd.DataFrame(columns=OUTPUT_COLUMNS), issues, source_label)

    missing_dates = int(out["date"].isna().sum())
    if missing_dates:
        issues.append(Issue("warning", f"{missing_dates} row(s) have no valid date and were left out."))
    missing_streams = int(out["streams"].isna().sum())
    if missing_streams:
        issues.append(Issue("warning", f"{missing_streams} row(s) have no stream count and were left out (they are not treated as zero)."))
    out = out[out["date"].notna() & out["streams"].notna()].copy()
    negatives = int((out["streams"] < 0).sum())
    if negatives:
        issues.append(Issue("warning", f"{negatives} negative stream count(s) found; check the export for adjustments or refunds."))
    if out.empty:
        issues.append(Issue("error", "No rows with both a valid date and a stream count were found."))
        return StreamIngestResult(pd.DataFrame(columns=OUTPUT_COLUMNS), issues, source_label)

    exact = int(out.duplicated(keep="first").sum())
    if exact:
        out = out.drop_duplicates(keep="first")
        issues.append(Issue("warning", f"{exact} identical repeated row(s) were removed so streams are not double counted."))

    out = _apply_defaults(out, mapping, issues, default_artist, default_track, default_dsp)
    out = _normalize_markets(out, mapping, issues)
    out = _assign_scope(out, mapping, default_scope, issues)
    out = _roll_up_to_days(out, issues)

    out["source_file"] = source_label
    out["artist"] = out["artist"].fillna("")
    out = out[OUTPUT_COLUMNS].reset_index(drop=True)
    return StreamIngestResult(out, issues, source_label)


def _apply_defaults(out, mapping, issues, default_artist, default_track, default_dsp):
    if out["track_title"].isna().all() and out["isrc"].isna().all():
        if default_track.strip():
            out["track_title"] = default_track.strip()
            issues.append(Issue("info", f"No track column in this file; all rows are treated as '{default_track.strip()}'."))
        else:
            out["track_title"] = "Unspecified track"
            issues.append(Issue("warning", "No track title or ISRC in this file and no track name was entered, so rows are labelled 'Unspecified track'."))
    if out["artist"].isna().all() and default_artist.strip():
        out["artist"] = default_artist.strip()
    out["isrc"] = out["isrc"].map(clean_isrc)
    bad_isrc = out["isrc"].notna() & (out["isrc"].fillna("").str.len() != 12)
    if bad_isrc.any():
        issues.append(Issue("warning", f"{int(bad_isrc.sum())} ISRC value(s) are not 12 characters; check the column mapping."))
    out["track_title"] = out["track_title"].fillna("Unspecified track")
    out["track_key"] = [make_track_key(i, t, a) for i, t, a in zip(out["isrc"], out["track_title"], out["artist"])]

    if out["dsp"].isna().all():
        if default_dsp.strip():
            out["dsp"] = dsp_label(default_dsp)
        else:
            out["dsp"] = "Unspecified"
            issues.append(Issue("info", "No DSP column in this file; rows are labelled 'Unspecified'."))
    else:
        out["dsp"] = [
            ALL_DSPS_LABEL if normalize_name(v).replace("_", " ") in TOTAL_DSP_LABELS else dsp_label(v)
            for v in out["dsp"].fillna("")
        ]
    return out


def _normalize_markets(out, mapping, issues):
    codes, labels, unmatched = [], [], set()
    for raw_market in out["market"]:
        code, label = normalize_market(raw_market)
        codes.append(code)
        labels.append(label)
        if code is None:
            unmatched.add(label)
    out["market_code"] = codes
    out["market"] = labels
    if unmatched:
        issues.append(
            Issue(
                "warning",
                "These country labels were not recognized and were kept as typed: "
                + ", ".join(sorted(unmatched)[:10])
                + ". They cannot be matched to paid media countries.",
            )
        )
    if mapping.get("market") is None:
        issues.append(Issue("info", "No country column in this file; streams are treated as 'All markets' and cannot be compared by country."))
    return out


def _assign_scope(out, mapping, default_scope, issues):
    has_source = mapping.get("source_name") is not None and out["source_name"].notna().any()
    if has_source:
        label = out["source_name"].fillna("").astype(str).str.strip().str.lower()
        is_total = label.isin(TOTAL_SOURCE_LABELS)
        out["scope"] = np.where(is_total, SCOPE_TOTAL, SCOPE_SOURCE)
        out["source_name"] = out["source_name"].where(~is_total, "All sources")
        n_source = int((~is_total).sum())
        if n_source:
            issues.append(
                Issue(
                    "info",
                    f"{n_source} row(s) belong to a specific playlist or source. They are kept separate from total track streams "
                    "and are never added to them.",
                )
            )
    else:
        out["scope"] = default_scope
        out["source_name"] = "All sources" if default_scope == SCOPE_TOTAL else "Unspecified source"
        if default_scope == SCOPE_SOURCE:
            issues.append(
                Issue(
                    "warning",
                    "This file was marked as playlist / source-attributed streams but has no playlist or source column. "
                    "These streams will not be used as total track streams.",
                )
            )
    return out


def _roll_up_to_days(out: pd.DataFrame, issues: list[Issue]) -> pd.DataFrame:
    """Daily analysis only: hourly rows are summed to a day when all 24 hours are present."""
    key = ["track_key", "market_code", "market", "dsp", "source_name", "scope", "artist", "track_title", "isrc"]
    out = out.copy()
    out["_day"] = out["date"].dt.normalize()
    group_cols = key + ["_day"]
    per_day = out.groupby(group_cols, dropna=False)["date"].nunique()
    hourly = bool((per_day > 1).mean() >= 0.5) if len(per_day) else False
    if hourly:
        hours = out.groupby(group_cols, dropna=False)["date"].transform("nunique")
        incomplete = hours < 24
        if incomplete.any():
            days = out.loc[incomplete, group_cols].drop_duplicates().shape[0]
            issues.append(
                Issue(
                    "warning",
                    f"Hourly data: {days} day(s) do not have all 24 hours and were left out of the daily analysis "
                    "so partial days do not look like drops in streaming.",
                )
            )
            out = out.loc[~incomplete]
        issues.append(Issue("info", "Hourly rows were added up into daily totals. Lollie analyses streaming day by day."))
        out["granularity"] = "hourly rolled up to daily"
    else:
        out["granularity"] = "daily"
        if out["date"].dt.normalize().ne(out["date"]).any():
            issues.append(Issue("info", "Some dates include a time of day; Lollie uses the calendar date."))

    grouped = out.groupby(group_cols, sort=False, dropna=False)
    sizes = grouped.size()
    if not hourly and (sizes > 1).any():
        issues.append(
            Issue(
                "info",
                f"{int((sizes > 1).sum())} day(s) had several rows for the same track, country, service and source; "
                "their streams were added together.",
            )
        )
    totals = grouped.agg(streams=("streams", "sum"), granularity=("granularity", "first")).reset_index()
    totals["date"] = totals["_day"]
    return totals.drop(columns=["_day"])


def combine_stream_frames(results: list[StreamIngestResult]) -> tuple[pd.DataFrame, list[Issue]]:
    """Merge several streaming imports without double counting."""
    issues: list[Issue] = []
    usable, seen = [], set()
    for result in results:
        if result.has_errors or result.frame.empty:
            continue
        if result.file_hash and result.file_hash in seen:
            issues.append(Issue("warning", f"'{result.source_label}' is identical to a file already imported and was skipped."))
            continue
        if result.file_hash:
            seen.add(result.file_hash)
        usable.append(result)
    if not usable:
        return pd.DataFrame(columns=OUTPUT_COLUMNS), issues

    combined = pd.concat([r.frame for r in usable], ignore_index=True)
    key = ["date", "track_key", "market_code", "market", "dsp", "source_name", "scope"]

    repeated = combined.duplicated(key, keep=False)
    if repeated.any():
        same_values = combined.duplicated(key + ["streams"], keep="first")
        if same_values.any():
            issues.append(Issue("warning", f"{int(same_values.sum())} row(s) appear in more than one file with identical values; counted once."))
            combined = combined.loc[~same_values]
        still = combined.duplicated(key, keep="last")
        if still.any():
            issues.append(
                Issue(
                    "warning",
                    f"{int(still.sum())} day(s) were reported with different stream counts in more than one file. "
                    "The value from the file listed last was kept; please check which export is correct.",
                )
            )
            combined = combined.loc[~still]

    combined, roll_issues = drop_rollup_rows(combined)
    issues.extend(roll_issues)
    return combined.sort_values(["date", "track_key", "market_code"]).reset_index(drop=True), issues


def drop_rollup_rows(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[Issue]]:
    """Remove 'All countries' / 'All DSPs' rows that sit on top of the detail rows they total."""
    issues: list[Issue] = []
    base = ["date", "track_key", "dsp", "source_name", "scope"]
    detail_market = frame["market_code"] != ALL_MARKETS_CODE
    has_detail = frame.assign(_d=detail_market).groupby(base)["_d"].transform("any")
    drop = ~detail_market & has_detail
    if drop.any():
        issues.append(
            Issue(
                "warning",
                f"{int(drop.sum())} 'All markets' row(s) were removed because country-level rows exist for the same track and day; "
                "keeping both would count streams twice.",
            )
        )
        frame = frame.loc[~drop]

    base = ["date", "track_key", "market_code", "source_name", "scope"]
    detail_dsp = frame["dsp"] != ALL_DSPS_LABEL
    has_detail = frame.assign(_d=detail_dsp).groupby(base)["_d"].transform("any")
    drop = ~detail_dsp & has_detail
    if drop.any():
        issues.append(
            Issue(
                "warning",
                f"{int(drop.sum())} 'All DSPs' row(s) were removed because service-level rows exist for the same track and day.",
            )
        )
        frame = frame.loc[~drop]
    return frame, issues


__all__ = [
    "ALL_DSPS_LABEL", "ALL_MARKETS_CODE", "ALL_MARKETS_LABEL", "NUMERIC_FIELDS", "OUTPUT_COLUMNS",
    "STREAM_HEADER_HINTS", "StreamIngestResult", "clean_isrc", "clean_title", "combine_stream_frames",
    "drop_rollup_rows", "file_fingerprint", "make_track_key", "normalize_stream_frame", "suggest_mapping",
]

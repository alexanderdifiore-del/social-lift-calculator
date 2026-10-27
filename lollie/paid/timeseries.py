"""Daily paid-media series, flight windows and overlap checks for the streaming chart."""

from __future__ import annotations

import pandas as pd

SERIES_COLUMNS = ["impressions", "views", "engagements", "clicks", "spend"]


def daily_series(frame: pd.DataFrame) -> pd.DataFrame:
    """Daily totals. Only real dated rows are used; nothing is interpolated."""
    dated = frame[frame["date"].notna()].copy()
    if dated.empty:
        return pd.DataFrame(columns=["date", *SERIES_COLUMNS])
    dated["date"] = dated["date"].dt.normalize()
    daily = dated.groupby("date")[SERIES_COLUMNS].sum(min_count=1).reset_index()
    return daily.sort_values("date").reset_index(drop=True)


def flights(frame: pd.DataFrame) -> pd.DataFrame:
    """Flight window per campaign (explicit start/end, else first/last reported day)."""
    rows = []
    for (platform, campaign), group in frame.groupby(["platform", "campaign_name"]):
        starts = group["start_date"].dropna()
        ends = group["end_date"].dropna()
        dates = group["date"].dropna()
        start = starts.min() if not starts.empty else (dates.min() if not dates.empty else pd.NaT)
        end = ends.max() if not ends.empty else (dates.max() if not dates.empty else pd.NaT)
        if pd.isna(start) or pd.isna(end):
            continue
        rows.append(
            {
                "platform": platform,
                "campaign": campaign,
                "start": start.normalize(),
                "end": end.normalize() + pd.Timedelta(days=1),
                "explicit": not starts.empty and not ends.empty,
            }
        )
    return pd.DataFrame(rows)


def overlap_report(daily: pd.DataFrame, stream_timestamps: pd.Series | None) -> list[str]:
    """Plain-language data-quality flags about how paid and streaming data line up."""
    notes: list[str] = []
    if daily.empty:
        notes.append("Paid media data has no dated rows, so spend cannot be placed on the timeline.")
        return notes
    if stream_timestamps is None or len(stream_timestamps) == 0:
        notes.append("No streaming data loaded, so paid activity is shown without a streaming comparison.")
        return notes
    stream_start = pd.to_datetime(stream_timestamps).min().normalize()
    stream_end = pd.to_datetime(stream_timestamps).max().normalize()
    paid_start, paid_end = daily["date"].min(), daily["date"].max()
    if paid_end < stream_start or paid_start > stream_end:
        notes.append("Paid media dates do not overlap the streaming data range.")
        return notes
    if paid_start < stream_start or paid_end > stream_end:
        notes.append("Paid media dates extend beyond the streaming data range; the chart only shows the overlapping period.")
    stream_days = set(pd.to_datetime(stream_timestamps).dt.normalize())
    missing = [d for d in pd.date_range(max(paid_start, stream_start), min(paid_end, stream_end)) if d not in stream_days]
    if missing:
        notes.append(f"Streaming data is missing for {len(missing)} day(s) inside the paid flight.")
    return notes

"""Expected-streams baseline and pre / during / post comparison.

How the expected line is calculated
-----------------------------------
1. Take the baseline window: the ``baseline_days`` days that end just before the
   campaign starts (optionally leaving ``gap_days`` days out right before launch).
2. Use only days that have streaming data. Missing days are never filled in.
3. If every weekday has at least ``MIN_PER_WEEKDAY`` observations, the expected
   value for a day is the *median of the same weekday* in the baseline window
   (so a Friday is compared with baseline Fridays). Otherwise it is the *median of
   all baseline days*.
4. The expected value is projected flat across the campaign and post-campaign
   windows. It is not adjusted for trends, seasonality beyond the weekday, new
   releases or anything else that changed, which is why results are described as
   observed change versus baseline and not as an effect of the ads.

Days without streaming data are left out of both the actual and the expected total
so a data gap cannot look like a drop or a gain.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MIN_PER_WEEKDAY = 3
METHOD_WEEKDAY = "Same-weekday median"
METHOD_OVERALL = "Overall median"
METHOD_NONE = "Not available"
DRIFT_THRESHOLD = 0.10


@dataclass
class AnalysisSettings:
    baseline_days: int = 28
    post_days: int = 14
    gap_days: int = 0
    min_baseline_days: int = 7


@dataclass
class WindowStats:
    label: str
    start: pd.Timestamp
    end: pd.Timestamp
    days_in_window: int
    days_with_data: int
    total: float | None
    average: float | None

    @property
    def coverage(self) -> float | None:
        return self.days_with_data / self.days_in_window if self.days_in_window else None


@dataclass
class WindowAnalysis:
    start: pd.Timestamp
    end: pd.Timestamp
    settings: AnalysisSettings
    baseline: WindowStats
    during: WindowStats
    post: WindowStats
    method: str
    method_text: str
    expected_value: float | None
    series: pd.DataFrame
    during_actual: float | None = None
    during_expected: float | None = None
    observed_change: float | None = None
    pct_change: float | None = None
    post_actual: float | None = None
    post_expected: float | None = None
    post_change: float | None = None
    post_pct_change: float | None = None
    flags: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.expected_value is not None and self.during.days_with_data > 0


def _stats(label: str, series: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> WindowStats:
    days = (end - start).days + 1 if end >= start else 0
    window = series.loc[start:end].dropna() if days else series.iloc[0:0]
    return WindowStats(
        label=label,
        start=start,
        end=end,
        days_in_window=days,
        days_with_data=int(window.shape[0]),
        total=float(window.sum()) if not window.empty else None,
        average=float(window.mean()) if not window.empty else None,
    )


def aggregate_daily(daily: pd.DataFrame, market_codes: list[str] | None = None) -> tuple[pd.Series, list[str]]:
    """One daily series for the chosen markets.

    A day only counts when every chosen market that reports at all in the date
    span reported it; otherwise the total would be too small and look like a drop.
    """
    notes: list[str] = []
    if daily.empty:
        return pd.Series(dtype=float), notes
    frame = daily if market_codes is None else daily[daily["market_code"].isin(market_codes)]
    if frame.empty:
        return pd.Series(dtype=float), notes
    per_day = frame.groupby("date").agg(streams=("streams", "sum"), markets=("market_code", "nunique"))
    expected = frame["market_code"].nunique()
    if expected > 1:
        incomplete = per_day["markets"] < expected
        if incomplete.any():
            notes.append(
                f"{int(incomplete.sum())} day(s) are missing streaming data for at least one country and were left out "
                "so the combined total is not understated."
            )
            per_day = per_day.loc[~incomplete]
    series = per_day["streams"].astype(float)
    series.index = pd.DatetimeIndex(series.index).normalize()
    return series.sort_index(), notes


def baseline_window(start: pd.Timestamp, settings: AnalysisSettings) -> tuple[pd.Timestamp, pd.Timestamp]:
    end = start - pd.Timedelta(days=1 + settings.gap_days)
    return end - pd.Timedelta(days=settings.baseline_days - 1), end


def compute_baseline(observed: pd.Series) -> tuple[str, str, dict[int, float] | float | None]:
    """Returns (method, plain-language description, weekday dict or flat value)."""
    if observed.empty:
        return METHOD_NONE, "No streaming data in the baseline window.", None
    weekday_counts = observed.groupby(observed.index.day_of_week).count()
    if len(weekday_counts) == 7 and (weekday_counts >= MIN_PER_WEEKDAY).all():
        medians = observed.groupby(observed.index.day_of_week).median()
        return (
            METHOD_WEEKDAY,
            f"Median streams for the same weekday across {len(observed)} baseline days "
            f"(at least {MIN_PER_WEEKDAY} per weekday).",
            {int(day): float(value) for day, value in medians.items()},
        )
    return (
        METHOD_OVERALL,
        f"Median daily streams across {len(observed)} baseline days "
        f"(some weekdays had fewer than {MIN_PER_WEEKDAY} days, so weekdays were not separated).",
        float(observed.median()),
    )


def _expected_for(dates: pd.DatetimeIndex, value: dict[int, float] | float | None) -> pd.Series:
    if value is None:
        return pd.Series(np.nan, index=dates)
    if isinstance(value, dict):
        return pd.Series([value.get(int(d.day_of_week), np.nan) for d in dates], index=dates)
    return pd.Series(float(value), index=dates)


def analyze_campaign_window(
    series: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
    settings: AnalysisSettings = AnalysisSettings(),
) -> WindowAnalysis:
    """Compare actual daily streams with the baseline before, during and after a campaign."""
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    if end < start:
        start, end = end, start
    b_start, b_end = baseline_window(start, settings)
    p_start, p_end = end + pd.Timedelta(days=1), end + pd.Timedelta(days=settings.post_days)

    baseline = _stats("Before campaign (baseline)", series, b_start, b_end)
    during = _stats("During campaign", series, start, end)
    post = _stats("After campaign", series, p_start, p_end) if settings.post_days > 0 else _stats("After campaign", series, p_start, p_start - pd.Timedelta(days=1))

    observed = series.loc[b_start:b_end].dropna()
    flags: list[str] = []
    if baseline.days_with_data < settings.min_baseline_days:
        method, text, value = METHOD_NONE, (
            f"Only {baseline.days_with_data} baseline day(s) have streaming data; at least "
            f"{settings.min_baseline_days} are needed, so no expected baseline is shown."
        ), None
        flags.append(text)
    else:
        method, text, value = compute_baseline(observed)
        if baseline.coverage is not None and baseline.coverage < 0.8:
            flags.append(
                f"The baseline window has streaming data for {baseline.days_with_data} of {baseline.days_in_window} days."
            )
        flags.extend(_drift_flag(observed))

    span = pd.date_range(b_start, p_end if settings.post_days > 0 else end)
    expected = _expected_for(span, value)
    frame = pd.DataFrame({"date": span, "actual": series.reindex(span).values, "expected": expected.values})
    frame["window"] = np.select(
        [frame["date"] < start, frame["date"] <= end],
        ["Before", "During"],
        default="After",
    )

    result = WindowAnalysis(
        start=start, end=end, settings=settings, baseline=baseline, during=during, post=post,
        method=method, method_text=text,
        expected_value=None if value is None else (float(np.mean(list(value.values()))) if isinstance(value, dict) else float(value)),
        series=frame, flags=flags,
    )
    if value is not None:
        for name, window in (("during", "During"), ("post", "After")):
            rows = frame[(frame["window"] == window) & frame["actual"].notna()]
            if rows.empty:
                continue
            actual, exp = float(rows["actual"].sum()), float(rows["expected"].sum())
            change = actual - exp
            pct = change / exp if exp > 0 else None
            setattr(result, f"{name}_actual", actual)
            setattr(result, f"{name}_expected", exp)
            if name == "during":
                result.observed_change, result.pct_change = change, pct
            else:
                result.post_change, result.post_pct_change = change, pct
    if during.coverage is not None and during.coverage < 0.8:
        flags.append(f"Streaming data covers {during.days_with_data} of {during.days_in_window} campaign days.")
    if post.days_in_window and post.coverage is not None and post.days_with_data == 0:
        flags.append("No streaming data after the campaign ended, so the post-campaign period cannot be assessed.")
    return result


def _drift_flag(observed: pd.Series) -> list[str]:
    if len(observed) < 8:
        return []
    half = len(observed) // 2
    first, second = observed.iloc[:half].median(), observed.iloc[-half:].median()
    if first <= 0:
        return []
    change = second / first - 1
    if abs(change) >= DRIFT_THRESHOLD:
        direction = "rising" if change > 0 else "falling"
        return [
            f"Streams were already {direction} before the campaign ({change:+.0%} between the first and second half of the "
            "baseline window), so a flat baseline may be too "
            + ("low" if change > 0 else "high")
            + " for the campaign period."
        ]
    return []


def trend_line(series: pd.Series, window: int = 7) -> pd.Series:
    """Centered rolling mean over days that have data (needs at least half the window)."""
    return series.rolling(window, min_periods=max(window // 2, 1), center=True).mean()


def label_change(pct: float | None) -> str:
    if pct is None or pd.isna(pct):
        return "Not available"
    if pct >= 0.10:
        return "Higher than baseline"
    if pct <= -0.10:
        return "Lower than baseline"
    return "Close to baseline"

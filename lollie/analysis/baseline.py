"""Expected-streams baseline and pre / during / post comparison for Global Catalog recordings.

How the expected line is calculated
-----------------------------------
1. Choose the history window: the 14, 28, 56 (preferred) or 90 days that end just before the
   campaign starts (optionally leaving ``gap_days`` out right before launch). "Auto" uses 56
   days when there is enough history and a shorter window otherwise.
2. Use only days that have streaming data, and only days *before* the campaign. Missing days
   are never filled in, and nothing from the campaign or after it can reach the baseline.
3. Fit the Global Catalog model (see ``catalog_model``): a median level, adjusted for the weekly
   pattern and, when the history shows a steady rise or fall, a damped gradual trend. Unusual
   spike days are set aside. The recording's normal day-to-day variability is measured from
   the same history.
4. Project that expected level across the campaign and the after-campaign window and compare.

Days without streaming data are left out of both the actual and the expected total so a data
gap cannot look like a drop or a gain. Results are described as observed change versus the
historical baseline, never as an effect of advertising.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from lollie.analysis.backtest import BacktestResult, backtest_baseline
from lollie.analysis.catalog_model import (
    BAND_WIDTH,
    METHOD_CATALOG,
    METHOD_NONE,
    NOT_ASSESSED,
    TREND_MIN_DAYS,
    WEEKDAY_MIN_DAYS,
    Assessment,
    BaselineModel,
    assess_change,
    fit_baseline,
)

WINDOW_CHOICES = (14, 28, 56, 90)
PREFERRED_WINDOW = 56
AUTO_CANDIDATES = (56, 28, 14)
AUTO_MIN_COVERAGE = 0.7
DRIFT_THRESHOLD = 0.10
SEASONAL_LAG_DAYS = 364
SEASONAL_NOTE_MIN = 0.03
CONCENTRATION_SHARE = 0.5
CONCENTRATION_DAYS = 3
MIN_CONCENTRATION_PERIOD = 7


@dataclass
class AnalysisSettings:
    baseline_days: int = PREFERRED_WINDOW
    post_days: int = 14
    gap_days: int = 0
    min_baseline_days: int = 7
    auto_window: bool = False
    use_trend: bool = True


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
    context: list[str] = field(default_factory=list)
    window_days: int = PREFERRED_WINDOW
    sigma_rel: float | None = None
    autocorrelation: float = 0.0
    assessment: Assessment | None = None
    post_assessment: Assessment | None = None
    model: BaselineModel | None = None
    backtest: BacktestResult | None = None
    extra_sigma_fn: object = field(default=None, repr=False)

    @property
    def usable(self) -> bool:
        return self.expected_value is not None and self.during.days_with_data > 0

    @property
    def reading(self) -> str:
        return self.assessment.reading if self.assessment is not None else "Not assessed"


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


def baseline_window(
    start: pd.Timestamp, settings: AnalysisSettings, window_days: int | None = None
) -> tuple[pd.Timestamp, pd.Timestamp]:
    days = settings.baseline_days if window_days is None else window_days
    end = start - pd.Timedelta(days=1 + settings.gap_days)
    return end - pd.Timedelta(days=days - 1), end


def resolve_window(series: pd.Series, start: pd.Timestamp, settings: AnalysisSettings) -> int:
    """Window length to use. With ``auto_window`` the longest of 56 / 28 / 14 days with enough history."""
    if not settings.auto_window:
        return settings.baseline_days
    for days in AUTO_CANDIDATES:
        b_start, b_end = baseline_window(start, settings, days)
        have = int(series.loc[b_start:b_end].dropna().shape[0])
        if have >= AUTO_MIN_COVERAGE * days:
            return days
    return PREFERRED_WINDOW


def _drift(observed: pd.Series) -> float | None:
    """Change between the first and second half of the history, when it is large enough to matter."""
    if len(observed) < 8:
        return None
    half = len(observed) // 2
    first, second = observed.iloc[:half].median(), observed.iloc[-half:].median()
    if first <= 0:
        return None
    change = second / first - 1
    return float(change) if abs(change) >= DRIFT_THRESHOLD else None


def _drift_flag(observed: pd.Series) -> list[str]:
    change = _drift(observed)
    if change is not None:
        direction = "rising" if change > 0 else "falling"
        return [
            f"Streams were already {direction} before the campaign ({change:+.0%} between the first and second half of the "
            "history window), and the history was too short to model a trend, so the baseline may be too "
            + ("low" if change > 0 else "high")
            + " for the campaign period."
        ]
    return []


def _concentration_flag(rows: pd.DataFrame) -> list[str]:
    if len(rows) < MIN_CONCENTRATION_PERIOD:
        return []
    diff = (rows["actual"] - rows["expected"]).astype(float)
    total = float(diff.sum())
    if total <= 0:
        return []
    top = diff.nlargest(CONCENTRATION_DAYS)
    if top.sum() / total > CONCENTRATION_SHARE and top.sum() > 0:
        days = ", ".join(f"{d:%b %d}" for d in rows.loc[top.index, "date"].sort_values())
        return [
            f"More than half of the observed increase comes from {CONCENTRATION_DAYS} days ({days}). A few high days can reflect "
            "a playlist add, a viral moment, press or another outside event rather than a sustained change."
        ]
    return []


def assemble_analysis(
    series: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
    settings: AnalysisSettings,
    window_days: int,
    *,
    expected: pd.Series | None,
    sigma_rel: float | None,
    autocorrelation: float,
    n_baseline_days: int,
    method: str,
    method_text: str,
    flags: list[str],
    context: list[str],
    model: BaselineModel | None = None,
    extra_sigma=None,
    residuals: pd.Series | None = None,
    backtest: BacktestResult | None = None,
) -> WindowAnalysis:
    """Turn an expected-streams series into the standard before / during / after analysis."""
    b_start, b_end = baseline_window(start, settings, window_days)
    p_start, p_end = end + pd.Timedelta(days=1), end + pd.Timedelta(days=settings.post_days)
    baseline = _stats("Before campaign (baseline)", series, b_start, b_end)
    during = _stats("During campaign", series, start, end)
    if settings.post_days > 0:
        post = _stats("After campaign", series, p_start, p_end)
    else:
        post = _stats("After campaign", series, p_start, p_start - pd.Timedelta(days=1))

    span = pd.date_range(b_start, p_end if settings.post_days > 0 else end)
    has_model = expected is not None and expected.notna().any()
    expected_values = expected.reindex(span).to_numpy(dtype=float) if has_model else np.full(len(span), np.nan)
    frame = pd.DataFrame({"date": span, "actual": series.reindex(span).to_numpy(dtype=float), "expected": expected_values})
    if has_model and sigma_rel is not None:
        frame["lower"] = np.maximum(frame["expected"] * (1 - BAND_WIDTH * sigma_rel), 0.0)
        frame["upper"] = frame["expected"] * (1 + BAND_WIDTH * sigma_rel)
    else:
        frame["lower"] = np.nan
        frame["upper"] = np.nan
    frame["window"] = np.select([frame["date"] < start, frame["date"] <= end], ["Before", "During"], default="After")

    result = WindowAnalysis(
        start=start, end=end, settings=settings, baseline=baseline, during=during, post=post,
        method=method, method_text=method_text, expected_value=None, series=frame,
        flags=list(flags), context=list(context), window_days=window_days, sigma_rel=sigma_rel,
        autocorrelation=autocorrelation, model=model, backtest=backtest, extra_sigma_fn=extra_sigma,
    )
    if has_model:
        for name, window in (("during", "During"), ("post", "After")):
            rows = frame[(frame["window"] == window) & frame["actual"].notna() & frame["expected"].notna()]
            if rows.empty:
                continue
            actual, exp = float(rows["actual"].sum()), float(rows["expected"].sum())
            change = actual - exp
            pct = change / exp if exp > 0 else None
            extra = float(extra_sigma(rows["date"])) if extra_sigma is not None else 0.0
            assessed = assess_change(
                actual, exp, len(rows), sigma_rel, autocorrelation, n_baseline_days, extra, residuals,
                backtest.rms_error if backtest is not None else None,
            )
            setattr(result, f"{name}_actual", actual)
            setattr(result, f"{name}_expected", exp)
            if name == "during":
                result.observed_change, result.pct_change, result.assessment = change, pct, assessed
                result.expected_value = float(rows["expected"].mean())
                result.flags.extend(_concentration_flag(rows))
            else:
                result.post_change, result.post_pct_change, result.post_assessment = change, pct, assessed
        if result.expected_value is None:
            result.expected_value = float(frame["expected"].dropna().mean())
    if during.coverage is not None and during.coverage < 0.8:
        result.flags.append(f"Streaming data covers {during.days_with_data} of {during.days_in_window} campaign days.")
    if post.days_in_window and post.coverage is not None and post.days_with_data == 0:
        result.flags.append("No streaming data after the campaign ended, so the post-campaign period cannot be assessed.")
    return result


def analyze_campaign_window(
    series: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
    settings: AnalysisSettings = AnalysisSettings(),
    *,
    seasonal_check: bool = True,
    run_backtest: bool = True,
) -> WindowAnalysis:
    """Compare actual daily streams with the Global Catalog baseline before, during and after a campaign."""
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    if end < start:
        start, end = end, start
    series = series.sort_index()
    window_days = resolve_window(series, start, settings)
    b_start, b_end = baseline_window(start, settings, window_days)
    observed = series.loc[b_start:b_end].dropna()
    n = int(observed.shape[0])
    flags: list[str] = []
    context: list[str] = []
    model: BaselineModel | None = None

    if n < settings.min_baseline_days:
        method, text = METHOD_NONE, (
            f"Only {n} history day(s) have streaming data before the campaign; at least "
            f"{settings.min_baseline_days} are needed, so no expected baseline is shown."
        )
        flags.append(text)
    else:
        model = fit_baseline(observed, b_end, use_trend=settings.use_trend)
        method, text = model.method, model.description
        days_in_window = (b_end - b_start).days + 1
        if n < 0.8 * days_in_window:
            if observed.index.min() > b_start + pd.Timedelta(days=3):
                flags.append(
                    f"Streaming history starts {observed.index.min():%b %d}, so only {n} of the {days_in_window} requested "
                    "history days are available."
                )
            else:
                flags.append(f"The history window has streaming data for {n} of {days_in_window} days.")
        if n < TREND_MIN_DAYS:
            context.append(
                f"With only {n} days of history Lollie cannot tell a gradual rise or fall from a change during the campaign. "
                "A longer history window (56 days is preferred) gives a more reliable baseline."
            )
        if n < WEEKDAY_MIN_DAYS:
            flags.append(
                f"Short history: only {n} days of data before the campaign. The baseline is a rough level without a weekly "
                "pattern or trend, so treat comparisons with caution."
            )
        if not model.trend_applied:
            flags.extend(_drift_flag(observed))
        elif model.trend_change is not None:
            direction = "rising" if model.trend_change > 0 else "falling"
            context.append(
                f"Streams were gradually {direction} before the campaign ({model.trend_change:+.0%} across the history window). "
                "The baseline follows that movement, fading it out over time, so ongoing growth or decline is not counted as a campaign change."
            )
        if model.spike_dates:
            shown = ", ".join(f"{d:%b %d}" for d in model.spike_dates[:4])
            more = "…" if len(model.spike_dates) > 4 else ""
            context.append(
                f"{len(model.spike_dates)} unusually high or low day(s) in the history window ({shown}{more}) were set aside "
                "when working out the baseline. They remain in the actual line."
            )

    drift_sigma = 0.0
    if model is not None and not model.trend_applied:
        drift = _drift(observed)
        drift_sigma = abs(drift) / 2 if drift is not None else 0.0

    def extra_sigma(dates: pd.Series) -> float:
        return float(np.hypot(drift_sigma, model.extrapolation_sigma(dates) if model else 0.0))

    backtest = None
    if model is not None and run_backtest:
        backtest = backtest_baseline(
            series, b_end, (end - start).days + 1, window_days, use_trend=settings.use_trend
        )

    expected = None
    if model is not None:
        span = pd.date_range(b_start, end + pd.Timedelta(days=max(settings.post_days, 0)))
        expected = model.predict(span)

    result = assemble_analysis(
        series, start, end, settings, window_days,
        expected=expected,
        sigma_rel=model.sigma_rel if model else None,
        autocorrelation=model.autocorrelation if model else 0.0,
        n_baseline_days=n,
        method=method, method_text=text, flags=flags, context=context, model=model, extra_sigma=extra_sigma,
        residuals=model.residuals if model else None, backtest=backtest,
    )
    if seasonal_check and result.usable:
        note = seasonal_note(series, start, end, settings, result)
        if note:
            result.context.append(note)
    return result


def seasonal_note(
    series: pd.Series, start: pd.Timestamp, end: pd.Timestamp, settings: AnalysisSettings, current: WindowAnalysis
) -> str | None:
    """Did the same calendar dates one year earlier also move versus their own baseline?"""
    lag = pd.Timedelta(days=SEASONAL_LAG_DAYS)
    year_ago = analyze_campaign_window(series, start - lag, end - lag, replace(settings, post_days=0), seasonal_check=False, run_backtest=False)
    if not year_ago.usable or year_ago.pct_change is None or (year_ago.during.coverage or 0) < 0.6:
        return None
    if abs(year_ago.pct_change) < SEASONAL_NOTE_MIN:
        return "Over the same dates one year earlier streams stayed close to their baseline, so a seasonal pattern is not obvious."
    direction = "above" if year_ago.pct_change > 0 else "below"
    return (
        f"Over the same dates one year earlier ({start - lag:%b %d} to {end - lag:%b %d}) streams ran "
        f"{abs(year_ago.pct_change):.0%} {direction} their own baseline, so part of this period's change may be seasonal."
    )


def trend_line(series: pd.Series, window: int = 7) -> pd.Series:
    """Centered rolling mean over days that have data (needs at least half the window)."""
    return series.rolling(window, min_periods=max(window // 2, 1), center=True).mean()


def label_change(pct: float | None) -> str:
    """Size-only label with fixed 10% cut-offs. Prefer ``WindowAnalysis.reading``, which uses the recording's own variability."""
    if pct is None or pd.isna(pct):
        return "Not available"
    if pct >= 0.10:
        return "Higher than baseline"
    if pct <= -0.10:
        return "Lower than baseline"
    return "Close to baseline"


__all__ = [
    "AnalysisSettings", "WindowStats", "WindowAnalysis", "WINDOW_CHOICES", "PREFERRED_WINDOW", "METHOD_CATALOG",
    "METHOD_NONE", "NOT_ASSESSED", "aggregate_daily", "baseline_window", "resolve_window", "analyze_campaign_window",
    "assemble_analysis", "trend_line", "label_change", "seasonal_note",
]

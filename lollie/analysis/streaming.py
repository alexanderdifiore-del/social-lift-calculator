"""Baselines for a promoted song, playlist or catalog selection.

Each track gets its own Global Catalog baseline (a track with a gentle upward drift and one that is
steady need different baselines). The expected and actual streams of the tracks that have a usable
baseline are then added up, so every track is counted once and a big track cannot hide a small one.
Tracks without enough history before the campaign are left out of the totals and named.

The same function is used for a DSP-specific view (for example Spotify only).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from lollie.analysis.backtest import backtest_baseline
from lollie.analysis.baseline import (
    AnalysisSettings,
    WindowAnalysis,
    aggregate_daily,
    analyze_campaign_window,
    assemble_analysis,
    baseline_window,
    resolve_window,
    seasonal_note,
)
from lollie.analysis.catalog_model import MAD_TO_SIGMA, MIN_SIGMA, lag1_autocorrelation
from lollie.streams.tracks import daily_scope_totals


@dataclass
class ScopeAnalysis:
    analysis: WindowAnalysis | None
    per_track: dict[str, WindowAnalysis] = field(default_factory=dict)
    titles: dict[str, str] = field(default_factory=dict)
    excluded: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def combined(self) -> bool:
        return len(self.per_track) > 1

    def track_table(self) -> pd.DataFrame:
        rows = []
        for key, title in self.titles.items():
            a = self.per_track.get(key)
            rows.append(
                {
                    "Track": title,
                    "Expected streams": a.during_expected if a else None,
                    "Actual streams": a.during_actual if a else None,
                    "Observed change": a.observed_change if a else None,
                    "Change vs baseline": a.pct_change if a else None,
                    "Reading": a.reading if a and a.usable else "Not enough history",
                }
            )
        return pd.DataFrame(rows, columns=["Track", "Expected streams", "Actual streams", "Observed change", "Change vs baseline", "Reading"])


def _track_series(
    matched: pd.DataFrame, tracks: pd.DataFrame, dsp: str | None, market_codes: list[str] | None
) -> tuple[dict[str, pd.Series], dict[str, str], list[str]]:
    series_by_key: dict[str, pd.Series] = {}
    titles: dict[str, str] = {}
    notes: list[str] = []
    for track in tracks.itertuples():
        mine = matched[matched["track_key"] == track.track_key]
        series, track_notes = aggregate_daily(daily_scope_totals(mine, dsp), market_codes)
        titles[track.track_key] = str(track.title)
        if series.empty:
            continue
        series_by_key[track.track_key] = series
        for note in track_notes:
            if note not in notes:
                notes.append(note)
    return series_by_key, titles, notes


def analyze_scope(
    matched: pd.DataFrame,
    tracks: pd.DataFrame,
    dsp: str | None,
    market_codes: list[str] | None,
    start: pd.Timestamp,
    end: pd.Timestamp,
    settings: AnalysisSettings,
) -> ScopeAnalysis:
    """Per-track baselines combined into one analysis for the whole selection."""
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    series_by_key, titles, notes = _track_series(matched, tracks, dsp, market_codes)
    if not series_by_key:
        return ScopeAnalysis(None, {}, titles, [], notes)
    if len(series_by_key) == 1:
        key, series = next(iter(series_by_key.items()))
        analysis = analyze_campaign_window(series, start, end, settings)
        return ScopeAnalysis(analysis, {key: analysis}, titles, [], notes)

    total = pd.concat(list(series_by_key.values()), axis=1).sum(axis=1, min_count=1)
    window = resolve_window(total, start, settings)
    fixed = replace(settings, baseline_days=window, auto_window=False)
    per_track = {k: analyze_campaign_window(s, start, end, fixed, seasonal_check=False) for k, s in series_by_key.items()}
    usable = {k: a for k, a in per_track.items() if a.model is not None and a.during.days_with_data > 0}
    excluded = [titles[k] for k in series_by_key if k not in usable]
    if len(usable) < 2:
        only = next(iter(usable)) if usable else None
        if only is not None:
            analysis = analyze_campaign_window(series_by_key[only], start, end, fixed)
            extra = [f"{len(excluded)} other track(s) did not have enough history before the campaign and are left out: " + ", ".join(excluded[:6]) + "."] if excluded else []
            return ScopeAnalysis(analysis, {only: per_track[only]}, titles, excluded, notes + extra)
        analysis = analyze_campaign_window(total.dropna(), start, end, fixed)
        return ScopeAnalysis(analysis, per_track, titles, excluded, notes)

    analysis = _combine(series_by_key, usable, start, end, fixed, window)
    if excluded:
        analysis.flags.append(
            f"{len(excluded)} track(s) did not have enough streaming history before the campaign for a baseline and are left out "
            "of the expected and actual totals: " + ", ".join(excluded[:6]) + ("…" if len(excluded) > 6 else "") + "."
        )
    seasonal = _combined_seasonal(series_by_key, usable, start, end, fixed)
    if seasonal:
        analysis.context.append(seasonal)
    return ScopeAnalysis(analysis, usable, titles, excluded, notes)


def _combine(
    series_by_key: dict[str, pd.Series],
    usable: dict[str, WindowAnalysis],
    start: pd.Timestamp,
    end: pd.Timestamp,
    settings: AnalysisSettings,
    window: int,
) -> WindowAnalysis:
    first = next(iter(usable.values()))
    span = pd.DatetimeIndex(first.series["date"])
    actual = pd.DataFrame({k: a.series.set_index("date")["actual"] for k, a in usable.items()}).reindex(span)
    expected = pd.DataFrame({k: a.series.set_index("date")["expected"] for k, a in usable.items()}).reindex(span)
    common = actual.notna().all(axis=1)
    combined_actual = actual.sum(axis=1).where(common).dropna()
    combined_expected = expected.sum(axis=1).where(common)

    b_start, b_end = baseline_window(start, settings, window)
    pre = pd.DatetimeIndex(span[(span >= b_start) & (span <= b_end)])
    resid = pd.DataFrame({k: a.model.residuals.reindex(pre) for k, a in usable.items()})
    weights = expected.reindex(pre)
    rel = (resid * weights).sum(axis=1, min_count=len(usable)) / weights.sum(axis=1)
    rel = rel.where(common.reindex(pre)).dropna()
    sigma_rel = max(MAD_TO_SIGMA * float(np.median(np.abs(rel - np.median(rel)))) if len(rel) else MIN_SIGMA, MIN_SIGMA)
    rho = lag1_autocorrelation(rel) if len(rel) else 0.0

    levels = expected.reindex(pd.date_range(start, end)).mean()
    share = levels / levels.sum() if levels.sum() > 0 else levels * 0 + 1 / len(levels)

    def extra_sigma(dates: pd.Series) -> float:
        return float(sum(share[k] * (a.extra_sigma_fn(dates) if a.extra_sigma_fn else 0.0) for k, a in usable.items()))

    history = pd.DataFrame({k: series_by_key[k] for k in usable})
    backtest = backtest_baseline(history, b_end, (end - start).days + 1, window, use_trend=settings.use_trend)
    n_base = int(common.reindex(pre).sum())
    method = first.method
    text = (
        f"Each of the {len(usable)} tracks has its own Global Catalog baseline from its own history "
        f"({window}-day window); expected and actual streams are then added up, each track counted once."
    )
    flags = [f for a in usable.values() for f in a.flags if f.startswith("Short history")][:1]
    return assemble_analysis(
        pd.Series(combined_actual), start, end, settings, window,
        expected=combined_expected, sigma_rel=sigma_rel, autocorrelation=rho, n_baseline_days=n_base,
        method=method, method_text=text, flags=flags, context=[], model=None, extra_sigma=extra_sigma,
        residuals=rel, backtest=backtest,
    )


def _combined_seasonal(
    series_by_key: dict[str, pd.Series], usable: dict[str, WindowAnalysis], start: pd.Timestamp, end: pd.Timestamp,
    settings: AnalysisSettings,
) -> str | None:
    frame = pd.DataFrame({k: series_by_key[k] for k in usable}).dropna()
    if frame.empty:
        return None
    total = frame.sum(axis=1)
    current = analyze_campaign_window(total, start, end, settings, seasonal_check=False, run_backtest=False)
    return seasonal_note(total, start, end, settings, current) if current.usable else None

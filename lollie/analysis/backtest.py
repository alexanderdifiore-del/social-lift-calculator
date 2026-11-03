"""Check the baseline against the recording's own past.

Pretend the campaign had started on earlier dates, build the baseline from only the days
before each pretend start, and see how far the expected streams were from what really
happened. Those misses are the honest measure of how much the baseline can be off for a
period of this length, so they feed the "normal variation" judgement and are shown to the user.

Rare spike days (a viral day, a reporting error) are set aside in the check, the same way they are when the baseline
itself is built, so normal variation describes ordinary ups and downs. Only data on or before ``history_end`` (the day before the real campaign's baseline window ends)
is used, so the real campaign period never enters the check.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from lollie.analysis.catalog_model import BAND_WIDTH, MIN_SIGMA, SPIKE_Z, fit_baseline

MAX_ORIGINS = 16
STEP_DAYS = 3
MIN_ORIGINS = 6
MIN_HISTORY_SHARE = 0.7
MIN_HORIZON_COVERAGE = 0.7


@dataclass
class BacktestResult:
    horizon_days: int
    window_days: int
    table: pd.DataFrame = field(default_factory=pd.DataFrame)
    note: str = ""

    @property
    def n_origins(self) -> int:
        return int(len(self.table))

    @property
    def usable(self) -> bool:
        return self.n_origins >= MIN_ORIGINS

    @property
    def rms_error(self) -> float | None:
        if not self.usable:
            return None
        return float(np.sqrt(np.mean(np.square(self.table["error"].to_numpy()))))

    @property
    def median_abs_error(self) -> float | None:
        return float(self.table["error"].abs().median()) if self.usable else None

    @property
    def naive_median_abs_error(self) -> float | None:
        return float(self.table["naive_error"].abs().median()) if self.usable else None

    @property
    def band_coverage(self) -> float | None:
        if not self.usable:
            return None
        weights = self.table["days"].to_numpy(dtype=float)
        return float(np.average(self.table["within_band"].to_numpy(dtype=float), weights=weights))

    @property
    def bias(self) -> float | None:
        return float(self.table["error"].mean()) if self.usable else None


def naive_flat_expected(observed: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """The simple flat baseline (same-weekday median, else overall median) used for comparison only."""
    observed = observed.dropna()
    if observed.empty:
        return pd.Series(np.nan, index=dates)
    by_day = observed.groupby(observed.index.day_of_week)
    if len(by_day) == 7 and (by_day.count() >= 3).all():
        medians = by_day.median()
        return pd.Series([medians[int(d)] for d in dates.day_of_week], index=dates)
    return pd.Series(float(observed.median()), index=dates)


def backtest_baseline(
    series: pd.Series | pd.DataFrame,
    history_end: pd.Timestamp,
    horizon_days: int,
    window_days: int,
    *,
    use_trend: bool = True,
    max_origins: int = MAX_ORIGINS,
    step_days: int = STEP_DAYS,
) -> BacktestResult:
    """Rolling-origin check of the baseline using only days up to ``history_end``.

    ``series`` is one recording's daily streams, or a table with one column per track. With several
    tracks each is fitted on its own and the expected streams are added up, exactly as in the
    live analysis.
    """
    history_end = pd.Timestamp(history_end).normalize()
    horizon_days = max(int(horizon_days), 1)
    frame = series.to_frame("streams") if isinstance(series, pd.Series) else series
    frame = frame[frame.index <= history_end].sort_index()
    result = BacktestResult(horizon_days=horizon_days, window_days=window_days)
    if frame.dropna(how="all").empty:
        result.note = "No history to check against."
        return result

    first_day = frame.dropna(how="all").index.min()
    candidate = history_end - pd.Timedelta(days=horizon_days - 1)
    origins = []
    while len(origins) < max_origins and candidate > first_day:
        origins.append(candidate)
        candidate -= pd.Timedelta(days=step_days)

    rows = []
    for origin in origins:
        fit_end = origin - pd.Timedelta(days=1)
        fit_start = fit_end - pd.Timedelta(days=window_days - 1)
        horizon = pd.date_range(origin, periods=horizon_days)
        actual = frame.reindex(horizon)
        valid = actual.notna().all(axis=1)
        if valid.mean() < MIN_HORIZON_COVERAGE:
            continue
        expected_daily = np.zeros(int(valid.sum()))
        naive_daily = np.zeros(int(valid.sum()))
        half_width = np.zeros(int(valid.sum()))
        ok = True
        for column in frame.columns:
            observed = frame[column].loc[fit_start:fit_end].dropna()
            if len(observed) < max(MIN_HISTORY_SHARE * window_days, 14):
                ok = False
                break
            model = fit_baseline(observed, fit_end, use_trend=use_trend)
            if model is None:
                ok = False
                break
            expected = model.predict(horizon)
            expected_daily += expected[valid].to_numpy()
            naive_daily += naive_flat_expected(observed, horizon)[valid].to_numpy()
            half_width += BAND_WIDTH * model.sigma_rel * expected[valid].to_numpy()
        if not ok:
            continue
        actual_daily = actual.sum(axis=1)[valid].to_numpy()
        with np.errstate(divide="ignore", invalid="ignore"):
            day_sigma = half_width / BAND_WIDTH / np.where(expected_daily > 0, expected_daily, np.nan)
            deviation = actual_daily / expected_daily - 1
            miss = np.abs(deviation - np.median(deviation))
        ordinary = miss <= SPIKE_Z * np.maximum(np.nan_to_num(day_sigma), MIN_SIGMA)
        if ordinary.mean() < MIN_HORIZON_COVERAGE:
            continue
        expected_total = float(expected_daily[ordinary].sum())
        naive_total = float(naive_daily[ordinary].sum())
        if expected_total <= 0 or naive_total <= 0:
            continue
        inside = (actual_daily >= np.maximum(expected_daily - half_width, 0.0)) & (actual_daily <= expected_daily + half_width)
        act_total = float(actual_daily[ordinary].sum())
        rows.append(
            {
                "origin": origin,
                "days": int(ordinary.sum()),
                "expected": expected_total,
                "actual": act_total,
                "error": act_total / expected_total - 1,
                "naive_error": act_total / naive_total - 1,
                "within_band": float(inside[ordinary].mean()),
            }
        )
    result.table = pd.DataFrame(rows).sort_values("origin").reset_index(drop=True) if rows else pd.DataFrame(
        columns=["origin", "days", "expected", "actual", "error", "naive_error", "within_band"]
    )
    if not result.usable:
        result.note = (
            f"Only {result.n_origins} earlier {horizon_days}-day period(s) had enough history to check the baseline "
            f"(at least {MIN_ORIGINS} are needed)."
        )
    return result

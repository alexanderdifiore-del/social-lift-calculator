"""Global Catalog baseline model: what "normal" looks like for one recording.

Established catalog recordings are not flat. They have weekly rhythm, slow growth or
decline, playlist placements, tours, anniversaries and the occasional viral moment.
The model below describes that normal level from the recording's own history, using
only days *before* the campaign, and measures how much it normally wobbles.

Plain-English recipe (every step is a standard robust statistic, nothing is tuned to a
particular catalog):

1. **Level.** The middle (median) daily streams in the history window, after removing the
   weekly pattern.
2. **Weekly pattern.** For each weekday, the median of that weekday's streams relative to the
   level (Fridays versus the average day, and so on). Used when every weekday has at least
   ``MIN_PER_WEEKDAY`` days of history.
3. **Gradual trend.** A straight line through the history (Theil-Sen: the median of all
   day-to-day slopes, so a few odd days cannot tilt it). Used only when the history is
   long enough, the rise or fall is steady and it adds up to at least ``TREND_MIN_CHANGE``
   across the window. Projected forward with damping (it fades, it is not assumed to
   continue forever) and capped.
4. **Spikes.** Days far away from this fitted pattern (more than ``SPIKE_Z`` robust
   standard deviations) are set aside and the pattern is refitted, so one viral day or one
   reporting outage does not bend the baseline. They stay visible in the actual line.
5. **Normal variability.** How far the recording's days normally land from the pattern,
   measured on the same history, as a percentage. This is what lets a +6% change be judged
   as large for a very stable song and unremarkable for a volatile one.

No universal growth or decay curve is assumed; the shape comes from the data or is left flat.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MIN_PER_WEEKDAY = 2
WEEKDAY_MIN_DAYS = 14
TREND_MIN_DAYS = 28
TREND_MIN_RHO = 0.4
TREND_MIN_CHANGE = 0.05
TREND_DAMPING = 0.99
TREND_PROJECTION_CAP = 0.25
SPIKE_Z = 3.5
MIN_SIGMA = 0.005
MAX_ITERATIONS = 4
MAX_SPIKE_SHARE = 0.15
EMPIRICAL_MIN_WINDOWS = 10
MAD_TO_SIGMA = 1.4826
MAX_AUTOCORRELATION = 0.8

METHOD_CATALOG = "Global Catalog baseline"
METHOD_NONE = "Not available"


@dataclass
class BaselineModel:
    """A fitted baseline. ``predict`` gives expected daily streams for any dates."""

    n_days: int
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    origin: pd.Timestamp
    intercept: float
    slope: float
    weekday_factors: dict[int, float] | None
    trend_applied: bool
    trend_change: float | None
    spike_dates: list[pd.Timestamp]
    sigma_rel: float
    autocorrelation: float
    n_params: int
    level_end: float
    t_mean: float = 0.0
    sxx: float = 0.0
    residuals: pd.Series | None = None
    components: list[str] = field(default_factory=list)

    @property
    def method(self) -> str:
        return METHOD_CATALOG

    @property
    def description(self) -> str:
        return (
            f"Median-based level from {self.n_days} history days"
            + "".join(f", {part}" for part in self.components)
            + "."
        )

    def extrapolation_sigma(self, dates: pd.Series | pd.DatetimeIndex) -> float:
        """Extra relative uncertainty from projecting a fitted trend beyond the history window."""
        if not self.trend_applied or self.sxx <= 0 or len(dates) == 0:
            return 0.0
        mid = float(np.mean((pd.DatetimeIndex(dates) - self.origin).days))
        return self.sigma_rel * abs(mid - self.t_mean) / float(np.sqrt(self.sxx))

    def _level(self, dates: pd.DatetimeIndex) -> np.ndarray:
        offset = (dates - self.origin).days.to_numpy(dtype=float)
        in_window = dates <= self.window_end
        levels = self.intercept + self.slope * offset
        if self.trend_applied:
            horizon = (dates - self.window_end).days.to_numpy(dtype=float)
            phi = TREND_DAMPING
            damped = np.where(horizon > 0, phi * (1 - phi ** np.maximum(horizon, 0)) / (1 - phi), 0.0)
            projected = self.level_end + self.slope * damped
            cap = self.level_end * TREND_PROJECTION_CAP
            projected = np.clip(projected, self.level_end - cap, self.level_end + cap)
            levels = np.where(in_window, levels, projected)
        else:
            levels = np.full(len(dates), self.intercept)
        return levels

    def predict(self, dates: pd.DatetimeIndex) -> pd.Series:
        dates = pd.DatetimeIndex(dates)
        levels = self._level(dates)
        if self.weekday_factors:
            factors = np.array([self.weekday_factors[int(d)] for d in dates.day_of_week])
            levels = levels * factors
        return pd.Series(np.maximum(levels, 0.0), index=dates)


def _theil_sen(t: np.ndarray, z: np.ndarray) -> tuple[float, float]:
    i, j = np.triu_indices(len(t), k=1)
    dt = t[j] - t[i]
    ok = dt > 0
    slope = float(np.median((z[j][ok] - z[i][ok]) / dt[ok])) if ok.any() else 0.0
    intercept = float(np.median(z - slope * t))
    return slope, intercept


def _robust_sigma(values: np.ndarray) -> float:
    if len(values) == 0:
        return MIN_SIGMA
    centre = np.median(values)
    return float(MAD_TO_SIGMA * np.median(np.abs(values - centre)))


def _leave_one_out_residuals(
    y: np.ndarray, dow: np.ndarray, keep: np.ndarray, level: np.ndarray
) -> np.ndarray:
    """Relative misses when each day's weekday factor is estimated *without* that day.

    A weekday factor fitted from a handful of days always matches those same days closely, which
    would make the recording look steadier than it is. Leaving each day out of its own factor gives
    an honest picture of how well the pattern predicts a day it has not seen.
    """
    ratio = y / level
    full = np.ones(7)
    for d in range(7):
        sel = keep & (dow == d)
        full[d] = np.median(ratio[sel]) if sel.any() else 1.0
    out = np.empty(len(y))
    for i in range(len(y)):
        factors = full.copy()
        others = keep & (dow == dow[i])
        others[i] = False
        if others.any():
            factors[dow[i]] = np.median(ratio[others])
        factors = factors / factors.mean()
        out[i] = y[i] / (level[i] * factors[dow[i]]) - 1.0
    return out


def lag1_autocorrelation(residuals: pd.Series) -> float:
    """Day-to-day carry-over of misses, from consecutive calendar days only."""
    previous = residuals.shift(1)
    consecutive = (residuals.index.to_series().diff().dt.days == 1).to_numpy()
    mask = consecutive & residuals.notna().to_numpy() & previous.notna().to_numpy()
    if mask.sum() < 10:
        return 0.0
    a, b = residuals.to_numpy()[mask], previous.to_numpy()[mask]
    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    return float(np.clip(np.corrcoef(a, b)[0, 1], 0.0, MAX_AUTOCORRELATION))


def fit_baseline(observed: pd.Series, window_end: pd.Timestamp, *, use_trend: bool = True) -> BaselineModel | None:
    """Fit the baseline to ``observed`` daily streams.

    Only observations on or before ``window_end`` are used, so nothing from the campaign
    can leak into the baseline even if the caller passes a longer series.
    """
    window_end = pd.Timestamp(window_end).normalize()
    y_series = observed.dropna().astype(float)
    y_series = y_series[y_series.index <= window_end]
    n = len(y_series)
    if n == 0:
        return None
    y = y_series.to_numpy()
    origin = y_series.index[0]
    t = (y_series.index - origin).days.to_numpy(dtype=float)
    dow = y_series.index.day_of_week.to_numpy()
    counts = np.bincount(dow, minlength=7)
    use_weekday = n >= WEEKDAY_MIN_DAYS and bool((counts >= MIN_PER_WEEKDAY).all())
    trend_possible = use_trend and n >= TREND_MIN_DAYS

    keep = np.ones(n, dtype=bool)
    factors = np.ones(7)
    state: dict = {}

    def fit_level(current_keep: np.ndarray) -> None:
        z = y / factors[dow]
        zk, tk = z[current_keep], t[current_keep]
        slope, intercept, applied, change = 0.0, float(np.median(zk)), False, None
        if trend_possible and len(zk) >= TREND_MIN_DAYS and np.ptp(tk) > 0:
            s, a = _theil_sen(tk, zk)
            mid = a + s * float(np.mean(tk))
            change = s * float(np.ptp(tk)) / mid if mid > 0 else None
            rho = pd.Series(tk).rank().corr(pd.Series(zk).rank())
            if change is not None and pd.notna(rho) and abs(rho) >= TREND_MIN_RHO and abs(change) >= TREND_MIN_CHANGE:
                slope, intercept, applied = s, a, True
        state.update(slope=slope, intercept=intercept, applied=applied, change=change)

    def level_at(tt: np.ndarray) -> np.ndarray:
        return np.maximum(state["intercept"] + state["slope"] * tt, 1e-9) if state["applied"] else np.full(len(tt), max(state["intercept"], 1e-9))

    def residuals() -> np.ndarray:
        return y / (level_at(t) * factors[dow]) - 1.0

    def update_factors(current_keep: np.ndarray) -> None:
        nonlocal factors
        ratio = y / level_at(t)
        updated = np.ones(7)
        for d in range(7):
            sel = current_keep & (dow == d)
            updated[d] = np.median(ratio[sel]) if sel.any() else 1.0
        factors = updated / updated.mean()

    def honest_residuals(current_keep: np.ndarray) -> np.ndarray:
        if use_weekday:
            return _leave_one_out_residuals(y, dow, current_keep, level_at(t))
        return residuals()

    for _ in range(MAX_ITERATIONS):
        fit_level(keep)
        if use_weekday:
            update_factors(keep)
        resid = honest_residuals(keep)
        centre = np.median(resid)
        sigma = max(_robust_sigma(resid), MIN_SIGMA)
        distance = np.abs(resid - centre)
        flagged = distance > SPIKE_Z * sigma
        limit = int(MAX_SPIKE_SHARE * n)
        if flagged.sum() > limit:
            cutoff = np.sort(distance)[::-1][limit] if limit < n else 0.0
            flagged = flagged & (distance > cutoff)
        new_keep = ~flagged
        if new_keep.sum() < max(7, int(0.6 * n)) or (new_keep == keep).all():
            break
        keep = new_keep
    fit_level(keep)
    if use_weekday:
        update_factors(keep)
    resid = honest_residuals(keep)
    sigma = max(_robust_sigma(resid[keep]), MIN_SIGMA)
    n_params = 1 + (6 if use_weekday else 0) + (1 if state["applied"] else 0)
    rho = lag1_autocorrelation(pd.Series(np.where(keep, resid, np.nan), index=y_series.index))

    t_end = float((window_end - origin).days)
    level_end = float(level_at(np.array([t_end]))[0])
    components = []
    if use_weekday:
        components.append("adjusted for the weekly pattern")
    if state["applied"]:
        direction = "rising" if state["slope"] > 0 else "falling"
        components.append(f"following the gradual {direction} trend ({state['change']:+.0%} across the window, projected with damping)")
    if (~keep).any():
        components.append(f"with {int((~keep).sum())} unusual day(s) set aside")
    if not use_weekday and n < WEEKDAY_MIN_DAYS:
        components.append("weekly pattern not separated (short history)")
    elif not use_weekday:
        components.append("weekly pattern not separated (some weekdays missing)")

    return BaselineModel(
        n_days=n,
        window_start=y_series.index[0],
        window_end=window_end,
        origin=origin,
        intercept=state["intercept"],
        slope=state["slope"] if state["applied"] else 0.0,
        weekday_factors={d: float(factors[d]) for d in range(7)} if use_weekday else None,
        trend_applied=bool(state["applied"]),
        trend_change=state["change"] if state["applied"] else None,
        spike_dates=[pd.Timestamp(d) for d in y_series.index[~keep]],
        sigma_rel=sigma,
        autocorrelation=rho,
        n_params=n_params,
        level_end=level_end,
        t_mean=float(np.mean(t[keep])),
        sxx=float(np.sum((t[keep] - np.mean(t[keep])) ** 2)),
        residuals=pd.Series(np.where(keep, resid, np.nan), index=y_series.index),
        components=components,
    )


NORMAL_VARIATION = "within"
ABOVE = "above"
BELOW = "below"
SLIGHTLY_ABOVE = "slightly_above"
SLIGHTLY_BELOW = "slightly_below"
NOT_ASSESSED = "not_assessed"

Z_BORDERLINE = 1.0
Z_OUTSIDE = 2.0
MIN_MATERIAL_CHANGE = 0.02
BAND_WIDTH = 2.0

READINGS = {
    ABOVE: "Above baseline, outside normal variation",
    SLIGHTLY_ABOVE: "Above baseline, borderline",
    NORMAL_VARIATION: "Within normal variation",
    SLIGHTLY_BELOW: "Below baseline, borderline",
    BELOW: "Below baseline, outside normal variation",
    NOT_ASSESSED: "Not assessed",
}


@dataclass
class Assessment:
    """How a campaign-period change compares with the recording's normal wobble."""

    pct_change: float | None
    sigma_period: float | None
    z_score: float | None
    status: str
    typical_swing: float | None

    @property
    def reading(self) -> str:
        return READINGS[self.status]


def empirical_period_sigma(residuals: pd.Series | None, n_days: int) -> float | None:
    """How far real ``n_days``-long stretches of this recording's history landed from its baseline.

    Root-mean-square of the average relative miss over every ``n_days`` stretch in the history.
    Needs enough overlapping stretches to be meaningful; otherwise returns None.
    """
    if residuals is None or n_days < 1 or residuals.dropna().empty:
        return None
    daily = residuals.reindex(pd.date_range(residuals.index.min(), residuals.index.max()))
    means = daily.rolling(n_days, min_periods=max(int(np.ceil(0.7 * n_days)), 1)).mean().dropna()
    if len(means) < EMPIRICAL_MIN_WINDOWS:
        return None
    return float(np.sqrt(np.mean(np.square(means.to_numpy()))))


def assess_change(
    actual: float | None,
    expected: float | None,
    n_days: int,
    sigma_rel: float | None,
    autocorrelation: float,
    n_baseline_days: int,
    extra_sigma: float = 0.0,
    residuals: pd.Series | None = None,
    backtest_sigma: float | None = None,
) -> Assessment:
    """Compare an observed change with normal variability. Descriptive, not a significance test.

    The spread of an average over ``n_days`` days is smaller than the daily spread, but misses
    on consecutive days tend to be alike, so the shrinkage is reduced by the measured
    day-to-day carry-over. The baseline level is itself estimated from limited history, which
    adds a second source of uncertainty. When the history is long enough, how far this same method
    missed on earlier stretches of the same length (``backtest_sigma``) sets a floor on the spread.
    ``extra_sigma`` widens the spread further when the baseline
    had to be projected along a trend or the history showed a drift that could not be modelled.
    """
    if actual is None or expected is None or expected <= 0 or sigma_rel is None or n_days <= 0:
        return Assessment(None, None, None, NOT_ASSESSED, None)
    pct = (actual - expected) / expected
    inflation = (1 + autocorrelation) / (1 - autocorrelation)
    parametric = sigma_rel * float(np.sqrt(inflation * (1.0 / n_days + 1.0 / max(n_baseline_days, 1))))
    empirical = empirical_period_sigma(residuals, n_days)
    sigma_period = float(np.sqrt(max(parametric, empirical or 0.0, backtest_sigma or 0.0) ** 2 + extra_sigma**2))
    z = pct / sigma_period if sigma_period > 0 else 0.0
    typical = BAND_WIDTH * sigma_period
    if abs(pct) < MIN_MATERIAL_CHANGE or abs(z) < Z_BORDERLINE:
        status = NORMAL_VARIATION
    elif abs(z) < Z_OUTSIDE:
        status = SLIGHTLY_ABOVE if pct > 0 else SLIGHTLY_BELOW
    else:
        status = ABOVE if pct > 0 else BELOW
    return Assessment(pct, sigma_period, z, status, typical)

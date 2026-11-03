"""SYNTHETIC Global Catalog scenarios used to test and explain the baseline.

Nothing here is real streaming data. Each scenario builds a daily streams series from a
known recipe (level, weekly pattern, trend, noise, spikes) and a known campaign-period
change, so tests can check that the baseline recovers what was put in.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

SYNTHETIC_LABEL = "Synthetic scenario for testing. Not real streaming data."
SCENARIO_START = pd.Timestamp("2026-01-01")
WEEKDAY_PATTERN = np.array([0.96, 0.97, 0.98, 1.0, 1.06, 1.05, 0.98])


@dataclass
class Scenario:
    name: str
    series: pd.Series
    campaign_start: pd.Timestamp
    campaign_end: pd.Timestamp
    campaign_effect: float
    notes: str = ""
    label: str = SYNTHETIC_LABEL
    extras: dict = field(default_factory=dict)


def _build(
    days: int,
    *,
    level: float = 10_000.0,
    noise: float = 0.015,
    weekday: np.ndarray | None = None,
    daily_growth: float = 0.0,
    annual_amplitude: float = 0.0,
    wander: float = 0.0,
    wave: tuple[float, float] | None = None,
    seed: int = 0,
    start: pd.Timestamp = SCENARIO_START,
) -> pd.Series:
    rng = np.random.default_rng(seed)
    index = pd.date_range(start, periods=days)
    t = np.arange(days)
    values = level * (1 + daily_growth) ** t
    if annual_amplitude:
        values = values * (1 + annual_amplitude * np.sin(2 * np.pi * t / 365.0))
    pattern = WEEKDAY_PATTERN if weekday is None else weekday
    values = values * pattern[index.day_of_week]
    if wave:
        amplitude, period = wave
        values = values * (1 + amplitude * np.sin(2 * np.pi * t / period))
    if wander:
        drift = np.zeros(days)
        for i in range(1, days):
            drift[i] = 0.9 * drift[i - 1] + rng.normal(0, wander)
        values = values * (1 + drift)
    values = values * (1 + rng.normal(0, noise, days))
    return pd.Series(values, index=index, dtype=float)


def _with_campaign(
    series: pd.Series, start: pd.Timestamp, length: int, effect: float, post_days: int = 14, post_effect: float = 0.0
) -> pd.Series:
    out = series.copy()
    during = pd.date_range(start, periods=length)
    out.loc[during] = out.loc[during] * (1 + effect)
    if post_days and post_effect:
        after = pd.date_range(during[-1] + pd.Timedelta(days=1), periods=post_days)
        out.loc[after] = out.loc[after] * (1 + post_effect)
    return out


def _scenario(name: str, base: pd.Series, campaign_start: str, length: int, effect: float, notes: str, **kwargs) -> Scenario:
    start = pd.Timestamp(campaign_start)
    series = _with_campaign(base, start, length, effect, **kwargs)
    return Scenario(name, series, start, start + pd.Timedelta(days=length - 1), effect, notes)


def stable_evergreen(effect: float = 0.0, seed: int = 1) -> Scenario:
    return _scenario(
        "Stable evergreen", _build(200, noise=0.012, seed=seed), "2026-05-01", 14, effect,
        "Very steady recording with a mild weekly pattern.",
    )


def weekly_fluctuation(effect: float = 0.0, seed: int = 2) -> Scenario:
    pattern = np.array([0.85, 0.88, 0.92, 1.0, 1.15, 1.30, 1.18])
    return _scenario(
        "Strong weekly pattern", _build(200, noise=0.02, weekday=pattern, seed=seed), "2026-05-01", 14, effect,
        "Weekends run about 30% above Mondays every week.",
    )


def gradual_growth(effect: float = 0.0, seed: int = 3) -> Scenario:
    return _scenario(
        "Gradual growth", _build(200, daily_growth=0.004, noise=0.015, seed=seed), "2026-05-01", 14, effect,
        "Streams have been climbing about 0.4% per day before and during the campaign window.",
    )


def gradual_decline(effect: float = 0.0, seed: int = 4) -> Scenario:
    return _scenario(
        "Gradual decline", _build(200, daily_growth=-0.004, noise=0.015, seed=seed), "2026-05-01", 14, effect,
        "Streams have been fading about 0.4% per day.",
    )


def seasonal(effect: float = 0.0, seed: int = 5) -> Scenario:
    """Two years of data with an annual cycle; the campaign repeats the seasonal climb of the year before."""
    base = _build(760, annual_amplitude=0.25, noise=0.012, seed=seed)
    return _scenario(
        "Seasonal", base, "2027-02-01", 21, effect,
        "Annual cycle (about 25% peak to average). The same dates one year earlier moved the same way.",
    )


def viral_spike_before(effect: float = 0.0, seed: int = 6) -> Scenario:
    base = _build(200, noise=0.015, seed=seed)
    spike = pd.date_range("2026-03-20", periods=3)
    base.loc[spike] = base.loc[spike] * np.array([4.0, 6.0, 3.0])
    scenario = _scenario("Viral spike before campaign", base, "2026-05-01", 14, effect, "A 3-day viral moment unrelated to ads, in the history window.")
    scenario.extras["spike_days"] = list(spike)
    return scenario


def viral_spike_during(seed: int = 7) -> Scenario:
    base = _build(200, noise=0.015, seed=seed)
    spike = pd.date_range("2026-05-06", periods=2)
    base.loc[spike] = base.loc[spike] * np.array([5.0, 7.0])
    scenario = _scenario("Viral spike during campaign", base, "2026-05-01", 14, 0.0, "No campaign effect; a 2-day viral moment lands inside the flight.")
    scenario.extras["spike_days"] = list(spike)
    return scenario


def small_change_stable(effect: float = 0.06, seed: int = 8) -> Scenario:
    return _scenario(
        "Small change, stable recording", _build(200, noise=0.012, seed=seed), "2026-05-01", 21, effect,
        "A 6% rise on a very stable recording.",
    )


def small_change_volatile(effect: float = 0.06, seed: int = 9) -> Scenario:
    return _scenario(
        "Small change, volatile recording", _build(200, noise=0.02, wave=(0.08, 23), seed=seed), "2026-05-01", 14, effect,
        "The same 6% rise on a recording whose level normally swings up and down by about 8% over a few weeks.",
    )


def negative_change(effect: float = -0.08, seed: int = 10) -> Scenario:
    return _scenario(
        "Negative observed change", _build(200, noise=0.012, seed=seed), "2026-05-01", 14, effect,
        "Streams ran 8% below the expected level during the campaign window.",
    )


def missing_history(days_of_history: int = 6, seed: int = 11) -> Scenario:
    start = pd.Timestamp("2026-05-01")
    base = _build(60, noise=0.015, seed=seed, start=start - pd.Timedelta(days=days_of_history))
    return _scenario("Missing history", base, "2026-05-01", 14, 0.0, f"Only {days_of_history} days exist before the campaign.")


def multi_track_playlist(seed: int = 12) -> dict[str, Scenario]:
    """Three tracks on a playlist with different levels, one of which moves during the flight."""
    tracks = {
        "Track A (synthetic)": (20_000.0, 0.010, 0.00),
        "Track B (synthetic)": (6_000.0, 0.030, 0.08),
        "Track C (synthetic)": (1_500.0, 0.050, 0.00),
    }
    out = {}
    for i, (name, (level, noise, effect)) in enumerate(tracks.items()):
        out[name] = _scenario(name, _build(200, level=level, noise=noise, seed=seed + i), "2026-05-01", 14, effect, "Playlist track.")
    return out


ALL_SINGLE = {
    "stable_evergreen": stable_evergreen,
    "weekly_fluctuation": weekly_fluctuation,
    "gradual_growth": gradual_growth,
    "gradual_decline": gradual_decline,
    "seasonal": seasonal,
    "viral_spike_before": viral_spike_before,
    "small_change_stable": small_change_stable,
    "small_change_volatile": small_change_volatile,
    "negative_change": negative_change,
}

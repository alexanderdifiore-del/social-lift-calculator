"""Global Catalog baseline checks on clearly labelled SYNTHETIC scenarios (see lollie/synthetic_scenarios.py)."""

import numpy as np
import pandas as pd
import pytest

from lollie import synthetic_scenarios as S
from lollie.analysis.backtest import backtest_baseline, naive_flat_expected
from lollie.analysis.baseline import (
    AnalysisSettings,
    analyze_campaign_window,
    baseline_window,
    resolve_window,
)
from lollie.analysis.catalog_model import (
    ABOVE,
    BELOW,
    NORMAL_VARIATION,
    assess_change,
    fit_baseline,
)
from lollie.summary import describe_change

DEFAULT = AnalysisSettings()


def run(scenario, **settings):
    return analyze_campaign_window(
        scenario.series, scenario.campaign_start, scenario.campaign_end, AnalysisSettings(**settings) if settings else DEFAULT
    )


def test_default_history_window_is_56_days_and_all_choices_work():
    assert AnalysisSettings().baseline_days == 56
    scenario = S.stable_evergreen()
    for days in (14, 28, 56, 90):
        result = run(scenario, baseline_days=days)
        assert result.window_days == days
        assert result.baseline.days_in_window == days
        assert result.usable


def test_auto_window_prefers_56_days_and_shortens_when_history_is_short():
    start = pd.Timestamp("2026-05-01")
    auto = AnalysisSettings(auto_window=True)
    long_history = pd.Series(1000.0, index=pd.date_range(start - pd.Timedelta(days=80), periods=100))
    assert resolve_window(long_history, start, auto) == 56
    thirty = pd.Series(1000.0, index=pd.date_range(start - pd.Timedelta(days=30), periods=50))
    assert resolve_window(thirty, start, auto) == 28
    twelve = pd.Series(1000.0, index=pd.date_range(start - pd.Timedelta(days=15), periods=40))
    assert resolve_window(twelve, start, auto) == 14
    assert resolve_window(long_history, start, AnalysisSettings(baseline_days=90)) == 90


def test_stable_evergreen_recovers_its_own_level_and_shows_no_change():
    scenario = S.stable_evergreen()
    result = run(scenario)
    assert abs(result.pct_change) < 0.01
    assert result.assessment.status == NORMAL_VARIATION
    assert result.model.weekday_factors is not None
    assert not result.model.trend_applied


def test_strong_weekly_pattern_is_not_mistaken_for_a_change():
    scenario = S.weekly_fluctuation()
    result = run(scenario)
    factors = result.model.weekday_factors
    assert factors[5] / factors[0] == pytest.approx(1.30 / 0.85, rel=0.05)
    assert abs(result.pct_change) < 0.02
    assert result.assessment.status == NORMAL_VARIATION


@pytest.mark.parametrize("factory,sign", [(S.gradual_growth, 1), (S.gradual_decline, -1)])
def test_gradual_growth_and_decline_are_followed_by_the_baseline(factory, sign):
    scenario = factory()
    result = run(scenario)
    assert result.model.trend_applied
    assert np.sign(result.model.slope) == sign
    assert abs(result.pct_change) < 0.03
    flat = naive_flat_expected(
        scenario.series.loc[result.baseline.start : result.baseline.end], pd.date_range(scenario.campaign_start, scenario.campaign_end)
    )
    actual = scenario.series.loc[scenario.campaign_start : scenario.campaign_end]
    flat_error = abs(actual.sum() / flat.sum() - 1)
    assert flat_error > 3 * abs(result.pct_change)
    assert any("gradually" in note for note in result.context)


def test_baseline_reflects_history_rather_than_a_universal_curve():
    growth, decline, flat = S.gradual_growth(), S.gradual_decline(), S.stable_evergreen()
    levels = [run(s).expected_value / s.series.loc[s.campaign_start : s.campaign_end].mean() for s in (growth, decline, flat)]
    for ratio in levels:
        assert ratio == pytest.approx(1.0, abs=0.03)


def test_seasonal_scenario_notes_the_same_dates_last_year():
    scenario = S.seasonal()
    result = run(scenario)
    notes = " ".join(result.context)
    assert "one year earlier" in notes
    assert abs(result.pct_change) < 0.04


def test_seasonal_note_is_absent_without_a_year_of_history():
    assert not any("one year earlier" in note for note in run(S.stable_evergreen()).context)


def test_viral_spike_before_the_campaign_does_not_bend_the_baseline():
    scenario = S.viral_spike_before()
    result = run(scenario)
    found = set(result.model.spike_dates)
    assert found & set(scenario.extras["spike_days"])
    assert abs(result.pct_change) < 0.02
    assert result.assessment.status == NORMAL_VARIATION
    assert any("set aside" in note for note in result.context)
    # the spike days stay visible in the actual line
    actual = result.series.set_index("date")["actual"]
    assert actual.loc[scenario.extras["spike_days"]].min() > 2.5 * result.expected_value


def test_viral_spike_during_the_campaign_is_called_out_as_concentrated():
    scenario = S.viral_spike_during()
    result = run(scenario)
    assert result.pct_change > 0.05
    assert any("More than half of the observed increase comes from 3 days" in flag for flag in result.flags)


def test_small_change_is_judged_against_the_recordings_own_variability():
    stable, volatile = S.small_change_stable(0.06), S.small_change_volatile(0.06)
    stable_result, volatile_result = run(stable), run(volatile)
    assert stable_result.pct_change == pytest.approx(0.06, abs=0.012)
    assert volatile_result.pct_change == pytest.approx(0.06, abs=0.04)
    assert stable_result.assessment.status == ABOVE
    assert volatile_result.assessment.status == NORMAL_VARIATION
    assert volatile_result.assessment.typical_swing > 3 * stable_result.assessment.typical_swing
    assert "outside" in stable_result.reading and "within" in volatile_result.reading.lower()


def test_wording_for_a_small_change_never_claims_the_campaign_generated_it():
    sentence = describe_change(run(S.small_change_stable(0.06)))
    assert "6" in sentence and "above the historical baseline during the campaign" in sentence
    assert "larger than this recording's normal variation" in sentence
    assert "generated" not in sentence.lower() and "caused" not in sentence.lower()
    volatile = describe_change(run(S.small_change_volatile(0.06)))
    assert "within this recording's normal variation" in volatile


def test_a_tiny_change_is_not_automatically_significant_even_when_the_history_is_very_steady():
    flat = pd.Series(1000.0, index=pd.date_range("2026-01-01", periods=120))
    result = analyze_campaign_window(flat, pd.Timestamp("2026-04-01"), pd.Timestamp("2026-04-14"))
    boosted = flat.copy()
    boosted.loc["2026-04-01":"2026-04-14"] *= 1.01
    small = analyze_campaign_window(boosted, pd.Timestamp("2026-04-01"), pd.Timestamp("2026-04-14"))
    assert result.assessment.status == NORMAL_VARIATION
    assert small.pct_change == pytest.approx(0.01)
    assert small.assessment.status == NORMAL_VARIATION


def test_negative_change_is_reported_neutrally():
    scenario = S.negative_change()
    result = run(scenario)
    assert result.pct_change < -0.06 and result.observed_change < 0
    assert result.assessment.status == BELOW
    sentence = describe_change(result)
    assert "below the historical baseline during the campaign" in sentence
    assert "loss" not in sentence.lower()


def test_missing_history_shows_a_warning_not_a_made_up_baseline():
    none = run(S.missing_history(days_of_history=3))
    assert not none.usable and none.expected_value is None and none.pct_change is None
    assert none.series["expected"].isna().all()
    assert any("history day" in flag for flag in none.flags)

    short = run(S.missing_history(days_of_history=10))
    assert short.usable
    assert short.model.weekday_factors is None
    assert any("Short history" in flag for flag in short.flags)


def test_campaign_and_later_data_never_leak_into_the_baseline():
    scenario = S.stable_evergreen(effect=0.0)
    base = run(scenario)
    tampered = scenario.series.copy()
    tampered.loc[scenario.campaign_start :] *= 5
    after = analyze_campaign_window(tampered, scenario.campaign_start, scenario.campaign_end)
    window = base.series["window"] == "Before"
    pd.testing.assert_series_equal(base.series.loc[window, "expected"], after.series.loc[window, "expected"])
    assert after.model.sigma_rel == base.model.sigma_rel
    assert after.during_expected == pytest.approx(base.during_expected)
    assert after.pct_change == pytest.approx(4.0, abs=0.05)


def test_days_before_the_history_window_do_not_matter():
    scenario = S.stable_evergreen()
    base = run(scenario, baseline_days=28)
    tampered = scenario.series.copy()
    tampered.loc[: base.baseline.start - pd.Timedelta(days=1)] = 1.0
    again = analyze_campaign_window(tampered, scenario.campaign_start, scenario.campaign_end, AnalysisSettings(baseline_days=28))
    assert again.during_expected == pytest.approx(base.during_expected)


def test_fit_ignores_observations_after_the_window_end():
    scenario = S.stable_evergreen()
    window_end = scenario.campaign_start - pd.Timedelta(days=1)
    clean = fit_baseline(scenario.series.loc[window_end - pd.Timedelta(days=55) : window_end], window_end)
    leaky = fit_baseline(scenario.series.loc[window_end - pd.Timedelta(days=55) :], window_end)
    dates = pd.date_range(scenario.campaign_start, periods=14)
    pd.testing.assert_series_equal(clean.predict(dates), leaky.predict(dates))


def test_variation_band_surrounds_the_expected_line():
    result = run(S.stable_evergreen())
    frame = result.series.dropna(subset=["expected"])
    assert (frame["lower"] < frame["expected"]).all() and (frame["upper"] > frame["expected"]).all()
    wide = run(S.small_change_volatile())
    assert (wide.series["upper"] / wide.series["expected"]).mean() > (frame["upper"] / frame["expected"]).mean()


def test_backtest_checks_the_method_on_earlier_history_only():
    scenario = S.stable_evergreen()
    history_end = scenario.campaign_start - pd.Timedelta(days=1)
    check = backtest_baseline(scenario.series, history_end, 14, 56)
    assert check.usable and check.n_origins >= 6
    assert check.median_abs_error < 0.02
    assert check.band_coverage > 0.85
    assert check.table["origin"].max() + pd.Timedelta(days=13) <= history_end
    tampered = scenario.series.copy()
    tampered.loc[scenario.campaign_start :] *= 9
    same = backtest_baseline(tampered, history_end, 14, 56)
    pd.testing.assert_frame_equal(check.table, same.table)


def test_backtest_shows_the_trend_aware_baseline_beats_a_flat_one_on_a_growing_recording():
    scenario = S.gradual_growth()
    check = backtest_baseline(scenario.series, scenario.campaign_start - pd.Timedelta(days=1), 14, 56)
    assert check.usable
    assert check.median_abs_error < check.naive_median_abs_error


def test_backtest_says_when_history_is_too_short():
    scenario = S.missing_history(days_of_history=30)
    check = backtest_baseline(scenario.series, scenario.campaign_start - pd.Timedelta(days=1), 14, 56)
    assert not check.usable and "at least" in check.note


def test_assess_change_widens_normal_variation_for_carried_over_misses():
    steady = assess_change(1060, 1000, 14, 0.02, 0.0, 56)
    carried = assess_change(1060, 1000, 14, 0.02, 0.7, 56)
    assert carried.typical_swing > steady.typical_swing
    assert carried.z_score < steady.z_score


def test_baseline_window_helper_accepts_an_explicit_window_length():
    start = pd.Timestamp("2026-05-01")
    assert baseline_window(start, DEFAULT) == (pd.Timestamp("2026-03-06"), pd.Timestamp("2026-04-30"))
    assert baseline_window(start, DEFAULT, 90)[0] == pd.Timestamp("2026-01-31")

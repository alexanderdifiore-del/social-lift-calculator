"""Playlist / multi-track analysis: per-track baselines, added up once, with market and DSP distinctions kept."""

import numpy as np
import pandas as pd
import pytest

from lollie import synthetic_scenarios as S
from lollie.analysis.baseline import AnalysisSettings, analyze_campaign_window
from lollie.analysis.streaming import analyze_scope
from lollie.streams.schema import SCOPE_SOURCE, SCOPE_TOTAL
from lollie.valuation import estimate_streaming_value

TRACKS = S.multi_track_playlist()
START, END = next(iter(TRACKS.values())).campaign_start, next(iter(TRACKS.values())).campaign_end
SETTINGS = AnalysisSettings(auto_window=True)


def stream_rows(series: pd.Series, key: str, title: str, market="US", dsp="Spotify", scope=SCOPE_TOTAL, source=""):
    return pd.DataFrame(
        {
            "date": series.index, "track_key": key, "track_title": title, "market_code": market,
            "market": {"US": "United States", "DE": "Germany"}[market], "dsp": dsp, "scope": scope,
            "source_name": source, "streams": series.values,
        }
    )


def playlist_frame(**kwargs) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, keys = [], []
    for i, (title, scenario) in enumerate(TRACKS.items()):
        rows.append(stream_rows(scenario.series, f"k{i}", title, **kwargs))
        keys.append({"track_key": f"k{i}", "title": title})
    return pd.concat(rows, ignore_index=True), pd.DataFrame(keys)


def test_totals_are_the_sum_of_per_track_baselines_with_each_track_counted_once():
    matched, tracks = playlist_frame()
    result = analyze_scope(matched, tracks, "Spotify", None, START, END, SETTINGS)
    combined = result.analysis
    assert result.combined and len(result.per_track) == 3
    assert combined.during_expected == pytest.approx(sum(a.during_expected for a in result.per_track.values()))
    assert combined.during_actual == pytest.approx(sum(a.during_actual for a in result.per_track.values()))
    truth = sum(s.series.loc[START:END].sum() for s in TRACKS.values())
    assert combined.during_actual == pytest.approx(truth)
    assert combined.observed_change == pytest.approx(combined.during_actual - combined.during_expected)


def test_each_track_keeps_its_own_baseline_and_reading():
    matched, tracks = playlist_frame()
    table = analyze_scope(matched, tracks, "Spotify", None, START, END, SETTINGS).track_table().set_index("Track")
    assert table.loc["Track B (synthetic)", "Change vs baseline"] == pytest.approx(0.08, abs=0.03)
    assert abs(table.loc["Track A (synthetic)", "Change vs baseline"]) < 0.03
    assert set(table.columns) >= {"Expected streams", "Actual streams", "Observed change", "Reading"}


def test_source_attributed_streams_are_not_added_to_the_totals():
    matched, tracks = playlist_frame()
    plain = analyze_scope(matched, tracks, "Spotify", None, START, END, SETTINGS).analysis
    first = TRACKS["Track A (synthetic)"].series
    extra = stream_rows(first * 0.2, "k0", "Track A (synthetic)", scope=SCOPE_SOURCE, source="Playlist X (synthetic)")
    with_source = analyze_scope(pd.concat([matched, extra], ignore_index=True), tracks, "Spotify", None, START, END, SETTINGS).analysis
    assert with_source.during_actual == pytest.approx(plain.during_actual)
    assert with_source.during_expected == pytest.approx(plain.during_expected)


def test_track_without_history_is_left_out_and_named_not_invented():
    matched, tracks = playlist_frame()
    newcomer = stream_rows(
        pd.Series(500.0, index=pd.date_range(START, periods=30)), "k9", "Brand New Track (synthetic)"
    )
    tracks = pd.concat([tracks, pd.DataFrame([{"track_key": "k9", "title": "Brand New Track (synthetic)"}])], ignore_index=True)
    result = analyze_scope(pd.concat([matched, newcomer], ignore_index=True), tracks, "Spotify", None, START, END, SETTINGS)
    assert result.excluded == ["Brand New Track (synthetic)"]
    assert "k9" not in result.per_track
    assert any("Brand New Track" in flag for flag in result.analysis.flags)
    table = result.track_table().set_index("Track")
    assert table.loc["Brand New Track (synthetic)", "Reading"] == "Not enough history"


def test_dsp_and_market_filters_are_respected():
    spotify, tracks = playlist_frame(dsp="Spotify")
    apple, _ = playlist_frame(dsp="Apple Music")
    apple["streams"] = apple["streams"] * 0.5
    germany, _ = playlist_frame(market="DE")
    matched = pd.concat([spotify, apple, germany], ignore_index=True)
    only_spotify = analyze_scope(matched, tracks, "Spotify", ["US"], START, END, SETTINGS).analysis
    only_apple = analyze_scope(matched, tracks, "Apple Music", ["US"], START, END, SETTINGS).analysis
    both = analyze_scope(matched, tracks, "All DSPs", ["US"], START, END, SETTINGS).analysis
    assert only_apple.during_actual == pytest.approx(0.5 * only_spotify.during_actual)
    assert both.during_actual == pytest.approx(only_spotify.during_actual + only_apple.during_actual)
    germany_only = analyze_scope(matched, tracks, "Spotify", ["DE"], START, END, SETTINGS).analysis
    assert germany_only.during_actual == pytest.approx(only_spotify.during_actual)


def test_value_uses_only_spotify_streams_in_a_mixed_dsp_selection():
    spotify, tracks = playlist_frame(dsp="Spotify")
    apple, _ = playlist_frame(dsp="Apple Music")
    apple["streams"] = apple["streams"] * 3
    matched = pd.concat([spotify, apple], ignore_index=True)
    all_dsps = analyze_scope(matched, tracks, "All DSPs", None, START, END, SETTINGS).analysis
    spot = analyze_scope(matched, tracks, "Spotify", None, START, END, SETTINGS).analysis
    value = estimate_streaming_value(spot.observed_change)
    assert value.value == pytest.approx(spot.observed_change * 0.004)
    assert abs(all_dsps.observed_change) > abs(spot.observed_change) * 2
    assert value.value != pytest.approx(all_dsps.observed_change * 0.004)


def test_single_track_scope_matches_a_direct_analysis():
    matched, tracks = playlist_frame()
    one = tracks.iloc[[0]]
    result = analyze_scope(matched, one, "Spotify", None, START, END, SETTINGS)
    direct = analyze_campaign_window(next(iter(TRACKS.values())).series, START, END, SETTINGS)
    assert not result.combined
    assert result.analysis.during_expected == pytest.approx(direct.during_expected)


def test_no_matching_streams_gives_no_analysis():
    matched, tracks = playlist_frame()
    assert analyze_scope(matched, tracks, "Deezer", None, START, END, SETTINGS).analysis is None


def test_combined_variation_band_and_reading_exist():
    matched, tracks = playlist_frame()
    combined = analyze_scope(matched, tracks, "Spotify", None, START, END, SETTINGS).analysis
    frame = combined.series.dropna(subset=["expected"])
    assert (frame["upper"] > frame["lower"]).all()
    assert combined.assessment is not None and combined.backtest is not None
    assert np.isfinite(combined.assessment.typical_swing)

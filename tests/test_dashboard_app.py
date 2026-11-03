"""End-to-end checks of the Lollie V2 dashboard using Streamlit's headless test runner."""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from lollie.demo import demo_paid_raw, demo_streams_raw, demo_track_list_raw

APP = str(Path(__file__).resolve().parent.parent / "social_lift_calculator.py")
REMOVED_TERMS = [
    "commerce", "e-commerce", "merch", "ad credits", "credit balance", "funding", "scenario lab", "upscal",
    "simulated lift", "lift multiplier", "artist tier", "campaign intensity",
]


def new_app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=90)


def page_text(at: AppTest) -> str:
    parts = []
    for group in (at.markdown, at.caption, at.warning, at.info, at.error, at.success, at.subheader, at.title, at.header):
        parts += [str(el.value) for el in group]
    parts += [str(m.label) for m in at.metric]
    parts += [str(w.label) for w in list(at.sidebar.checkbox) + list(at.sidebar.selectbox) + list(at.sidebar.slider)]
    parts += [str(w.label) for w in list(at.selectbox) + list(at.multiselect) + list(at.radio) + list(at.checkbox)]
    return " ".join(parts).lower()


def test_default_view_is_an_empty_real_data_dashboard():
    at = new_app().run()
    assert not at.exception
    assert "nothing is loaded yet" in page_text(at)
    assert not at.metric
    assert not at.sidebar.toggle[0].value


def test_demo_mode_shows_all_five_sections_and_is_labelled_synthetic():
    at = new_app()
    at.session_state["lollie_demo_mode"] = True
    at.run()
    assert not at.exception
    text = page_text(at)
    for heading in ("a · campaign overview", "b · paid media performance", "c · streaming intelligence", "d · market comparison", "e · campaign summary"):
        assert heading in text
    assert "synthetic" in text and "demo mode" in text
    labels = [m.label for m in at.metric]
    assert "Spend" in labels and {"Expected Streams", "Actual Streams", "Observed Streaming Change", "Percentage Change vs. Baseline"} <= set(labels)


def test_turning_demo_off_removes_all_demo_data():
    at = new_app()
    at.session_state["lollie_demo_mode"] = True
    at.run()
    at.session_state["lollie_demo_mode"] = False
    at.run()
    assert not at.exception
    assert not at.metric
    assert "demo artist" not in page_text(at)


@pytest.mark.parametrize("demo", [False, True])
def test_commerce_credits_and_upscaling_are_gone_from_the_visible_app(demo):
    at = new_app()
    at.session_state["lollie_demo_mode"] = demo
    at.run()
    text = page_text(at)
    for term in REMOVED_TERMS:
        assert term not in text, term


def test_uploading_one_paid_media_report_and_one_streaming_report():
    at = new_app().run()
    at.sidebar.file_uploader(key="paid_upload").upload("wavo.csv", demo_paid_raw().to_csv(index=False).encode())
    at.sidebar.file_uploader(key="stream_upload").upload("streams.csv", demo_streams_raw().to_csv(index=False).encode())
    at.run()
    assert not at.exception
    text = page_text(at)
    assert "189 rows read" in text and "daily rows read" in text
    assert not any("demo mode" in w.value.lower() for w in at.warning)
    labels = [m.label for m in at.metric]
    assert {"Campaign start", "Spend", "Expected Streams", "Actual Streams", "Observed Streaming Change"} <= set(labels)
    assert at.selectbox(key="f_campaign").value.startswith("DEMO | Neon Skyline")


def test_paid_report_alone_shows_paid_sections_and_asks_for_streaming():
    at = new_app().run()
    at.sidebar.file_uploader(key="paid_upload").upload("wavo.csv", demo_paid_raw().to_csv(index=False).encode())
    at.run()
    assert not at.exception
    assert "Spend" in [m.label for m in at.metric]
    assert "no streaming report loaded" in page_text(at)


def test_streaming_report_alone_asks_for_campaign_dates():
    at = new_app().run()
    at.sidebar.file_uploader(key="stream_upload").upload("streams.csv", demo_streams_raw().to_csv(index=False).encode())
    at.run()
    assert not at.exception
    assert "enter campaign start and end dates" in page_text(at)


def test_playlist_campaign_with_an_uploaded_track_list():
    at = new_app().run()
    at.sidebar.file_uploader(key="paid_upload").upload("wavo.csv", demo_paid_raw().to_csv(index=False).encode())
    at.sidebar.file_uploader(key="stream_upload").upload("streams.csv", demo_streams_raw().to_csv(index=False).encode())
    at.sidebar.file_uploader(key="track_upload").upload("tracks.csv", demo_track_list_raw().to_csv(index=False).encode())
    at.run()
    at.selectbox(key="f_campaign").set_value("DEMO | Summer Playlist push").run()
    assert not at.exception
    text = page_text(at)
    assert "using the uploaded track list: 3 track(s)" in text
    labels = [m.label for m in at.metric]
    assert "Actual Streams" in labels
    assert any("track membership is not marked as verified" in c.value.lower() for c in at.caption)


def test_unreadable_streaming_file_is_explained_not_a_crash():
    at = new_app().run()
    at.sidebar.file_uploader(key="stream_upload").upload("bad.csv", b"hello,world\nfoo,bar\n")
    at.run()
    assert not at.exception
    assert any("date" in e.value.lower() for e in at.error)


def test_streaming_file_without_country_or_track_columns_still_works():
    streams = demo_streams_raw()
    one = streams[
        (streams["Track Title"] == "Neon Skyline") & (streams["Country"] == "United States")
        & (streams["DSP"] == "Spotify") & (streams["Playlist / Source"] == "Total")
    ][["Date", "Streams"]]
    at = new_app().run()
    at.sidebar.file_uploader(key="paid_upload").upload("wavo.csv", demo_paid_raw().to_csv(index=False).encode())
    at.sidebar.file_uploader(key="stream_upload").upload("streams.csv", one.to_csv(index=False).encode())
    at.run()
    assert not at.exception
    assert "no country column" in page_text(at)
    assert "Percentage Change vs. Baseline" in [m.label for m in at.metric]


def demo_app() -> AppTest:
    at = new_app()
    at.session_state["lollie_demo_mode"] = True
    return at.run()


def metric_value(at: AppTest, label: str):
    return next(m.value for m in at.metric if m.label == label)


def sidebar_checkbox(at: AppTest, label: str):
    return next(c for c in at.sidebar.checkbox if c.label == label)


def test_headline_cards_are_expected_actual_change_percentage_and_optional_value():
    at = demo_app()
    labels = [m.label for m in at.metric]
    for label in ("Expected Streams", "Actual Streams", "Observed Streaming Change", "Percentage Change vs. Baseline", "Estimated Streaming Value Change"):
        assert label in labels
    for gone in ("Before campaign", "During campaign", "After campaign", "Change versus baseline"):
        assert gone not in labels


def test_streaming_value_is_the_observed_spotify_change_times_the_default_rate():
    at = demo_app()
    value = metric_value(at, "Estimated Streaming Value Change")
    assert value.startswith("+$") or value.startswith("-$")
    shown = float(value.replace("$", "").replace(",", "").replace("+", ""))
    at.sidebar.number_input(key="value_rate").set_value(0.008).run()
    doubled = float(metric_value(at, "Estimated Streaming Value Change").replace("$", "").replace(",", "").replace("+", ""))
    assert doubled == pytest.approx(shown * 2, rel=0.01)
    expected_streams = metric_value(at, "Expected Streams")
    assert expected_streams == next(m.value for m in at.metric if m.label == "Expected Streams")


def test_changing_the_rate_never_changes_expected_streams():
    at = demo_app()
    before = (metric_value(at, "Expected Streams"), metric_value(at, "Actual Streams"), metric_value(at, "Observed Streaming Change"))
    at.sidebar.number_input(key="value_rate").set_value(0.05).run()
    after = (metric_value(at, "Expected Streams"), metric_value(at, "Actual Streams"), metric_value(at, "Observed Streaming Change"))
    assert before == after


def test_streaming_value_can_be_turned_off_entirely():
    at = demo_app()
    sidebar_checkbox(at, "Show the estimate").set_value(False).run()
    assert not at.exception
    assert "Estimated Streaming Value Change" not in [m.label for m in at.metric]
    assert "estimated streaming value change:" not in page_text(at)


def test_value_is_not_calculated_for_a_service_the_rate_does_not_cover():
    at = demo_app()
    at.selectbox(key="f_dsp").set_value("Apple Music").run()
    assert not at.exception
    assert metric_value(at, "Estimated Streaming Value Change") == "Not calculated"
    assert "applies to spotify streams only" in page_text(at)


def test_advanced_settings_are_collapsed_by_default_and_hold_the_statistical_options():
    at = new_app().run()
    advanced = next(e for e in at.sidebar.expander if e.label == "Advanced Settings")
    assert not advanced.proto.expanded
    labels = [w.label for w in list(at.sidebar.checkbox) + list(at.sidebar.number_input)]
    assert "Show typical range from history" in labels
    assert "Assumed value per Spotify stream (USD)" in labels
    assert at.sidebar.number_input(key="value_rate").value == 0.004


def test_history_window_choices_default_to_auto_56_days():
    at = new_app().run()
    window = next(s for s in at.sidebar.selectbox if s.label == "Historical baseline window")
    assert window.value.startswith("Auto")
    assert window.options[1:] == ["14 days", "28 days", "56 days", "90 days"]


def test_each_history_window_choice_runs_cleanly_in_demo_mode():
    at = demo_app()
    for choice in ("14 days", "28 days", "90 days", "56 days"):
        window = next(s for s in at.sidebar.selectbox if s.label == "Historical baseline window")
        window.set_value(choice).run()
        assert not at.exception, choice
        assert "Expected Streams" in [m.label for m in at.metric]


def test_variation_band_toggle_runs_cleanly():
    at = demo_app()
    sidebar_checkbox(at, "Show typical range from history").set_value(False).run()
    assert not at.exception
    sidebar_checkbox(at, "Let the baseline follow a gradual rise or fall").set_value(False).run()
    assert not at.exception


def test_summary_uses_historical_baseline_language_and_never_claims_causation():
    at = demo_app()
    text = page_text(at)
    assert "above the historical baseline during the campaign" in text
    assert "normal variation" in text
    assert "estimated streaming value change" in text
    text = re.sub(r"show (that )?the (campaign|ads|advertising) caused", "", text)
    for claim in ("campaign generated", "ads generated", "advertising generated", "campaign caused", "ads caused"):
        assert claim not in text
    assert "not wmg revenue" in text.replace("\\", "")


def test_production_mode_never_contains_synthetic_records():
    at = new_app()
    at.session_state["lollie_demo_mode"] = True
    at.run()
    at.session_state["lollie_demo_mode"] = False
    at.run()
    assert not at.exception and not at.metric
    at.sidebar.file_uploader(key="paid_upload").upload("wavo.csv", demo_paid_raw().to_csv(index=False).encode())
    at.run()
    assert not at.exception
    assert not at.sidebar.toggle[0].value
    text = page_text(at)
    assert "synthetic demo data" not in text

"""End-to-end checks of the Lollie V2 dashboard using Streamlit's headless test runner."""

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
    assert "Spend" in labels and "Observed streaming change" in labels and "Change versus baseline" in labels


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
    assert {"Campaign start", "Spend", "Before campaign", "During campaign"} <= set(labels)
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
    assert "During campaign" in labels
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
    assert "Change versus baseline" in [m.label for m in at.metric]

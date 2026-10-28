"""End-to-end checks of the unified dashboard using Streamlit's headless AppTest."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "social_lift_calculator.py")


@pytest.fixture()
def fresh_app(tmp_path, monkeypatch):
    monkeypatch.setenv("LOLLIE_DB_PATH", str(tmp_path / "dash.db"))
    return AppTest.from_file(APP, default_timeout=90)


def _all_text(at: AppTest) -> str:
    parts = []
    for collection in (at.markdown, at.caption, at.info, at.warning, at.error, at.subheader, at.title, at.text):
        parts.extend(str(element.value) for element in collection)
    parts.extend(f"{m.label} {m.value}" for m in at.metric)
    return "\n".join(parts)


def _metrics(at: AppTest) -> dict:
    return {m.label: m.value for m in at.metric}


def _radio(at: AppTest, label: str):
    return next(r for r in at.sidebar.radio if r.label == label)


def test_production_default_shows_no_simulated_numbers(fresh_app):
    at = fresh_app.run()
    assert not at.exception
    metrics = _metrics(at)
    assert metrics["Paid Spend"] == "n/a"
    assert metrics["Streaming Lift (24h)"] == "n/a"
    assert metrics["Product Revenue"] == "n/a"
    text = _all_text(at)
    assert "148,717" not in text and "DEMO MODE" not in text
    for section in ["A · Campaign Overview", "B · Paid Media Performance", "C · Streaming Impact Analysis",
                    "D · Audience & Creative Performance", "E · Commerce Revenue", "F · Ad Credits & Funding"]:
        assert section in text


def test_demo_mode_reproduces_original_streaming_and_commerce_numbers(fresh_app):
    at = fresh_app
    at.session_state["lollie_demo_mode"] = True
    at.run()
    assert not at.exception
    metrics = _metrics(at)
    assert metrics["Hourly Baseline Rate"] == "2,740"
    assert metrics["Actual Streams (24h)"] == "148,717"
    assert metrics["Expected Streams (24h)"] == "65,367"
    assert metrics["Estimated Social Lift"] == "83,350"
    assert metrics["Attributed Product Revenue"] == "$13,198"
    assert metrics["Estimated Net Revenue"] == "$7,397"
    assert metrics["Attributed Units Sold"] == "410"
    assert metrics["Revenue per 1K Social Views"] == "$15.53"
    assert "DEMO MODE" in _all_text(at)


def test_paid_media_lives_on_the_same_page_as_streaming_and_commerce(fresh_app):
    at = fresh_app
    at.session_state["lollie_demo_mode"] = True
    at.run()
    metrics = _metrics(at)
    for label in ["Impressions", "Spend", "Budget Pacing", "CPM", "CTR", "Actual Streams (24h)", "Attributed Product Revenue"]:
        assert label in metrics
    assert {"Ahead of goal", "On track", "At risk", "Forecast unavailable"} <= set(metrics)
    assert len(at.get("plotly_chart")) >= 2


def test_manual_entry_drives_the_streaming_totals(fresh_app):
    at = fresh_app.run()
    _radio(at, "Data Source Mode").set_value("Manual entry").run()
    for number in at.sidebar.number_input:
        if number.label == "Manual Expected Streams":
            number.set_value(1000)
        if number.label == "Manual Actual Streams":
            number.set_value(1500)
    at.run()
    assert not at.exception
    metrics = _metrics(at)
    assert metrics["Expected Streams (24h)"] == "1,000"
    assert metrics["Actual Streams (24h)"] == "1,500"
    assert metrics["Estimated Social Lift"] == "500"


def test_turning_demo_off_removes_all_simulated_data(fresh_app):
    at = fresh_app
    at.session_state["lollie_demo_mode"] = True
    at.run()
    at.session_state["lollie_demo_mode"] = False
    at.run()
    assert not at.exception
    metrics = _metrics(at)
    assert metrics["Paid Spend"] == "n/a" and "Actual Streams (24h)" not in metrics


def test_credits_section_is_collapsed_and_compact(fresh_app):
    at = fresh_app.run()
    credits = [e for e in at.expander if e.label == "Ad Credits & Funding"]
    assert credits and not credits[0].proto.expanded


def test_video_upscaling_is_gone_from_the_whole_project():
    offenders = []
    for path in ROOT.rglob("*"):
        if path.suffix not in {".py", ".md", ".txt", ".json"} or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.name == "test_dashboard_app.py":
            continue
        if "upscal" in path.read_text(errors="ignore").lower():
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_advanced_credit_tools_open_without_errors(fresh_app):
    at = fresh_app
    at.session_state["lollie_demo_mode"] = True
    at.session_state["credits_advanced"] = True
    at.run()
    assert not at.exception
    assert "Programs" in [tab.label for tab in at.tabs]


def test_manual_commerce_rows_start_at_zero_in_production_and_drive_revenue(fresh_app):
    at = fresh_app.run()
    _radio(at, "Commerce Data Mode").set_value("Manual dated sales entries").run()
    assert not at.exception
    assert _metrics(at)["Product Revenue"] == "n/a"
    units = next(n for n in at.sidebar.number_input if n.label == "Units Sold")
    units.set_value(10)
    at.run()
    assert not at.exception
    metrics = _metrics(at)
    assert metrics["Attributed Units Sold"] == "10"
    assert metrics["Attributed Product Revenue"].startswith("$")
    assert metrics["Revenue per 1K Social Views"] == "n/a"

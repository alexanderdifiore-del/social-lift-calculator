"""Radio statistics are not part of Lollie. Lollie covers paid media and digital streaming only."""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "social_lift_calculator.py")
FORBIDDEN = [
    "airplay", "spins", "radio station", "station performance", "radio reach", "radio audience", "radio chart",
    "radio impression", "radio market", "radio attribution", "radio stat", "broadcast",
]
# The Streamlit selection widget is called "radio"; it is a UI control, not a statistic.
WIDGET = re.compile(r"\b(st|sidebar|at|container|col\w*)\.radio\b|\.radio\(|_radio\b|\bat\.sidebar\.radio\b")


def live_sources():
    for folder in ("lollie",):
        yield from (ROOT / folder).rglob("*.py")
    yield ROOT / "social_lift_calculator.py"
    yield ROOT / "app.py"
    yield from (ROOT / "docs").glob("*.md")
    yield ROOT / "README.md"
    yield ROOT / "requirements.txt"


def test_live_code_and_docs_have_no_radio_statistics():
    offenders = []
    for path in live_sources():
        text = WIDGET.sub("", path.read_text(encoding="utf-8")).lower()
        if path.name == "limitations_and_questions.md" or path.name == "README.md":
            text = text.replace("radio statistics are not part of lollie", "")
        for term in FORBIDDEN + ["radio"]:
            if term in text and not _allowed(path, term, text):
                offenders.append(f"{path.relative_to(ROOT)}: {term}")
    assert not offenders, offenders


def _allowed(path: Path, term: str, text: str) -> bool:
    """Documentation may state that radio is excluded; code may not mention it at all."""
    if path.suffix == ".md":
        return all(
            "radio" not in line or "no radio" in line or "radio is" in line or "radio statistics" in line or "radio data" in line
            for line in text.splitlines()
            if term in line
        )
    return False


def test_no_radio_python_modules_or_sample_columns():
    names = [p.name.lower() for p in (ROOT / "lollie").rglob("*") if p.is_file()]
    assert not [n for n in names if "radio" in n or "airplay" in n]
    for sample in (ROOT / "sample_data").glob("*.csv"):
        header = sample.read_text(encoding="utf-8").splitlines()[0].lower()
        assert "radio" not in header and "spins" not in header and "airplay" not in header


@pytest.mark.parametrize("demo", [False, True])
def test_visible_dashboard_never_mentions_radio(demo):
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["lollie_demo_mode"] = demo
    at.run()
    assert not at.exception
    parts = []
    for group in (at.markdown, at.caption, at.warning, at.info, at.error, at.subheader, at.title, at.header):
        parts += [str(el.value) for el in group]
    parts += [str(m.label) for m in at.metric]
    parts += [str(w.label) for w in list(at.sidebar.checkbox) + list(at.sidebar.selectbox) + list(at.sidebar.slider)]
    parts += [str(w.label) for w in list(at.selectbox) + list(at.multiselect) + list(at.checkbox)]
    text = " ".join(parts).lower()
    for term in ("radio", "airplay", "spins", "station"):
        assert term not in text, term

"""Shared Lollie visual identity for Streamlit apps."""

import streamlit as st

LOLLIE_TITLE_CSS = """
    .lollie-title {
        font-size: 4.4rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        color: #00a8b8;
        margin-bottom: 0.1rem;
        text-shadow:
            0 0 6px rgba(0, 168, 184, 0.35),
            0 0 14px rgba(0, 168, 184, 0.22),
            0 0 24px rgba(0, 168, 184, 0.14);
        font-family: "Helvetica Neue", Arial, sans-serif;
    }

    .lollie-subtitle {
        font-size: 0.95rem;
        color: #008a99;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-top: -0.4rem;
        margin-bottom: 2rem;
        font-weight: 700;
        text-shadow:
            0 0 4px rgba(0, 168, 184, 0.18);
    }
"""


def render_lollie_header(
    subtitle: str = "streaming • commerce • video asset intelligence",
) -> None:
    """Render the Lollie title block and optional subtitle."""
    st.markdown(
        f"""
        <style>{LOLLIE_TITLE_CSS}</style>
        <div class="lollie-title">lollie</div>
        <div class="lollie-subtitle">{subtitle}</div>
        """,
        unsafe_allow_html=True,
    )

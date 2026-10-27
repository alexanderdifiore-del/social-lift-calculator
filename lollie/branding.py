"""Shared Lollie visual identity for Streamlit apps."""

from __future__ import annotations

import html

import streamlit as st

LOLLIE_TITLE_CSS = """
.lollie-header-wrap {
    margin-bottom: 1.5rem;
}
.lollie-header-wrap .lollie-title {
    font-size: 4.4rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    color: #00a8b8 !important;
    margin: 0 0 0.1rem 0;
    line-height: 1.05;
    text-shadow:
        0 0 6px rgba(0, 168, 184, 0.35),
        0 0 14px rgba(0, 168, 184, 0.22),
        0 0 24px rgba(0, 168, 184, 0.14);
    font-family: "Helvetica Neue", Arial, sans-serif;
}
.lollie-header-wrap .lollie-subtitle {
    font-size: 0.95rem;
    color: #008a99 !important;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin: 0 0 0.5rem 0;
    font-weight: 700;
    text-shadow: 0 0 4px rgba(0, 168, 184, 0.18);
}
"""


def render_lollie_header(
    subtitle: str = "streaming • commerce • video asset intelligence",
) -> None:
    """Render the Lollie title block and optional subtitle.

    Uses ``st.html`` so Streamlit does not strip custom ``div`` markup (a common
    issue with ``st.markdown(..., unsafe_allow_html=True)`` on newer Streamlit).
    """
    safe_subtitle = html.escape(subtitle)
    block = f"""
<style>{LOLLIE_TITLE_CSS}</style>
<div class="lollie-header-wrap">
  <div class="lollie-title">lollie</div>
  <div class="lollie-subtitle">{safe_subtitle}</div>
</div>
"""
    if hasattr(st, "html"):
        st.html(block)
    else:
        st.markdown(block, unsafe_allow_html=True)

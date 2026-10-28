"""Original Lollie teal branding."""

import textwrap

import streamlit as st

HEADER_HTML = textwrap.dedent(
    """
    <style>
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

    .lollie-section {
        font-size: 1.35rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #008a99;
        font-family: 'Helvetica Neue', Arial, sans-serif;
        margin-top: 0.75rem;
        margin-bottom: 1.5rem;
    }
    </style>

    <div class="lollie-title">lollie</div>
    <div class="lollie-subtitle">{subtitle}</div>
    """
)

SECTION_HTML = '<div class="lollie-section">{text}</div>'


def render_lollie_header(subtitle: str = "paid media • streaming intelligence") -> None:
    st.markdown(HEADER_HTML.replace("{subtitle}", subtitle), unsafe_allow_html=True)


def render_section_title(text: str) -> None:
    st.markdown(SECTION_HTML.format(text=text), unsafe_allow_html=True)

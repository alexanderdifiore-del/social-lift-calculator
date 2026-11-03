"""Small helpers so Lollie runs on slightly older Streamlit builds."""

from __future__ import annotations

import streamlit as st


def plotly_chart(figure) -> None:
    try:
        st.plotly_chart(figure, width="stretch")
    except TypeError:
        st.plotly_chart(figure, use_container_width=True)


def reading_label(text: str) -> None:
    if hasattr(st, "badge"):
        try:
            st.badge(text)
            return
        except TypeError:
            pass
    st.markdown(f"**{text}**")

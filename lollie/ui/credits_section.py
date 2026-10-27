"""Compact Ad Credits & Funding section for the unified dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from lollie.credits.metrics import build_inventory_dataframe, expiration_warnings
from lollie.credits.service import CreditService
from lollie.credits.settings import load_warning_settings
from lollie.credits.ui_components import (
    credit_filters_sidebar,
    render_allocations_tab,
    render_import_tab,
    render_inventory_tab,
    render_programs_tab,
    render_settings_tab,
    render_warning_banner,
)

UNIT_SUFFIX = {"USD": "", "impressions": " impr.", "share_percent": "%", "other": ""}


def _amount(value, unit: str) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    if unit == "USD":
        return f"${value:,.0f}"
    if unit == "share_percent":
        return f"{value:,.1f}%"
    if unit == "impressions":
        return f"{value:,.0f} impr."
    if unit == "other":
        return f"{value:,.0f}"
    return f"{value:,.0f} {unit}"


def get_service() -> CreditService:
    if "credit_service" not in st.session_state:
        st.session_state.credit_service = CreditService()
    return st.session_state.credit_service


def render_credits_compact(demo_mode: bool, *, artist: str = "", campaign: str = "") -> None:
    """Collapsed summary of funding available to the campaign."""
    service = get_service()
    overview = service.funding_overview(include_demo=demo_mode)

    with st.expander("Ad Credits & Funding", expanded=False):
        st.caption(
            "Three kinds of funding are kept separate: **in-kind partner funding** (allocations from TikTok, Spotify, "
            "Snap, YouTube), **billing credits** (reduce an invoice) and **prepaid funds** (paid upfront, reimbursed later). "
            "Amounts are only what has been entered or imported; nothing is redeemed or pulled from ad accounts automatically."
        )
        if demo_mode:
            st.caption("Demo mode is on, so synthetic demo credit records can appear here.")

        if overview.empty:
            st.info(
                "No credits or funding have been recorded yet. Open **Advanced credit tools** below to record a partner "
                "allocation or import billing credits."
            )
        else:
            shown = overview.copy()
            for column in ["Credit amount", "Allocated", "Utilized", "Remaining"]:
                shown[column] = [_amount(value, unit) for value, unit in zip(overview[column], overview["Unit"])]
            shown = shown.drop(columns=["Unit"])
            related = shown["Artist"].str.lower().eq(artist.strip().lower()) if artist.strip() else None
            st.dataframe(shown, width="stretch", hide_index=True)
            if related is not None and related.any():
                st.caption(f"{int(related.sum())} line(s) are linked to {artist}.")
            st.caption(
                "Amounts in different units (USD, impressions, share %) or currencies are never added together. "
                "Planned allocations do not reduce actual billed cost; only verified utilization does."
            )

        credits = service.list_credits(include_demo=demo_mode)
        warnings = expiration_warnings(credits, load_warning_settings()) if credits else []
        if warnings:
            render_warning_banner(warnings[:3])

        advanced = st.toggle("Advanced credit tools (edit, record utilization, import, reconcile)", key="credits_advanced")
        if advanced:
            if demo_mode:
                left, right = st.columns(2)
                if left.button("Load synthetic demo credit records"):
                    service.load_demo_records()
                    st.rerun()
                if right.button("Clear demo credit records"):
                    service.clear_demo_records()
                    st.rerun()
            filters = credit_filters_sidebar(service, target=st, include_demo=demo_mode)
            tabs = st.tabs(
                [
                    "Programs",
                    "Allocations & utilization",
                    "Billing credits",
                    "Import billing credits",
                    "Settings",
                ]
            )
            with tabs[0]:
                render_programs_tab(service)
            with tabs[1]:
                render_allocations_tab(service, filters)
            with tabs[2]:
                render_inventory_tab(service, filters)
            with tabs[3]:
                render_import_tab(service)
            with tabs[4]:
                render_settings_tab()

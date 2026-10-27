"""Ad Credits & Funding — Lollie paid media intelligence."""

import streamlit as st

from lollie.branding import render_lollie_header
from lollie.credits.service import CreditService
from lollie.credits.ui_components import (
    credit_filters_sidebar,
    render_allocations_tab,
    render_import_tab,
    render_inventory_tab,
    render_programs_tab,
    render_project_requests_tab,
    render_settings_tab,
)

st.set_page_config(
    page_title="Ad Credits & Funding | lollie",
    layout="wide",
)

render_lollie_header("ad credits & funding")

st.markdown(
    """
Track **partner-funded ad credit allocations** for Global Catalog — TikTok, Spotify, YouTube,
Snapchat, and Meta — plus any **billing-level promotional credits** that reduce invoiced spend.

These are **in-kind partner allocations** (quarterly budgets, impression grants, match capacity,
share-of-pool). Use this dashboard to track commitments and reported delivery — your internal
project request process stays the same.
"""
)

if "credit_service" not in st.session_state:
    st.session_state.credit_service = CreditService()

service: CreditService = st.session_state.credit_service

with st.sidebar:
    st.divider()
    st.subheader("Demo mode")
    st.caption("Synthetic data for training only — never mixed into production totals unless enabled.")
    if st.button("Load synthetic demo records"):
        service.load_demo_records()
        st.success("Demo records loaded. Enable **Include demo records** in filters to view them.")
    if st.button("Clear demo records"):
        service.clear_demo_records()
        st.info("Demo records removed.")

filters = credit_filters_sidebar(service)

tab_programs, tab_requests, tab_allocations, tab_legacy, tab_import, tab_settings = st.tabs(
    [
        "Programs",
        "Project requests",
        "Allocations & utilization",
        "Billing credits (legacy)",
        "Import billing credits",
        "Advanced settings",
    ]
)

with tab_programs:
    render_programs_tab(service)
with tab_requests:
    render_project_requests_tab(service)
with tab_allocations:
    render_allocations_tab(service, filters)
with tab_legacy:
    render_inventory_tab(service, filters)
with tab_import:
    render_import_tab(service)
with tab_settings:
    render_settings_tab()

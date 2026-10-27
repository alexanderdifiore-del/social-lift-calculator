"""Ad Credits & Funding — Lollie paid media intelligence."""

import streamlit as st

from lollie.branding import render_lollie_header
from lollie.credits.service import CreditService
from lollie.credits.ui_components import (
    credit_filters_sidebar,
    render_allocation_tab,
    render_cost_tab,
    render_import_tab,
    render_inventory_tab,
    render_register_tab,
    render_settings_tab,
)

st.set_page_config(
    page_title="Ad Credits & Funding | lollie",
    layout="wide",
)

render_lollie_header("ad credits & funding")

st.markdown(
    """
Track **promotional advertising credits** across Meta, TikTok, Google/YouTube, and Snapchat.
Monitor balances, expiration, eligibility, and **verified** utilization alongside gross media spend.

WAVO and other consolidated reports can be imported when they include promotional credit fields — 
Lollie does not assume undocumented platform API access.
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

tab_inventory, tab_register, tab_import, tab_allocate, tab_cost, tab_settings = st.tabs(
    [
        "Inventory dashboard",
        "Register credit",
        "Import CSV / Excel",
        "Allocate & reconcile",
        "Cost analysis",
        "Advanced settings",
    ]
)

with tab_inventory:
    render_inventory_tab(service, filters)
with tab_register:
    render_register_tab(service)
with tab_import:
    render_import_tab(service)
with tab_allocate:
    render_allocation_tab(service, filters)
with tab_cost:
    render_cost_tab(service, filters)
with tab_settings:
    render_settings_tab()

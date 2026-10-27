"""Compare paid media scenarios — Lollie v2."""

import pandas as pd
import streamlit as st

from lollie.branding import render_lollie_header
from lollie.constants import PAID_CHANNEL_DEFAULTS
from lollie.paid_media import build_paid_media_plan, channel_efficiency_table

st.set_page_config(page_title="Scenario Lab | lollie", layout="wide")

render_lollie_header("scenario lab • paid media")

st.markdown(
    "Run **low / base / high** spend scenarios with the same channel mix "
    "to compare efficiency and total incremental streams."
)

with st.sidebar:
    artist_tier = st.selectbox(
        "Artist Tier",
        ["Emerging", "Mid-tier", "Established", "Superstar"],
        index=1,
        key="scenario_tier",
    )
    primary_market = st.selectbox(
        "Primary Market",
        ["US", "Global", "Europe", "LATAM", "APAC"],
        key="scenario_market",
    )
    base_budget = st.number_input("Base budget ($)", 5000.0, 500000.0, 20000.0, 1000.0)
    low_factor = st.slider("Low scenario (% of base)", 10, 90, 50)
    high_factor = st.slider("High scenario (% of base)", 110, 300, 175)
    intensity = st.slider("Campaign intensity (all scenarios)", 1, 10, 6)

    st.divider()
    st.caption("Channel mix weights")
    weights = {
        ch: st.slider(ch, 0, 100, 25, key=f"mix_{ch}") for ch in PAID_CHANNEL_DEFAULTS
    }

scenarios = {
    "Low": base_budget * (low_factor / 100),
    "Base": base_budget,
    "High": base_budget * (high_factor / 100),
}

summary_rows = []
detail_frames = []

for label, budget in scenarios.items():
    plan = build_paid_media_plan(
        total_budget_usd=budget,
        channel_budgets=weights,
        campaign_intensity=float(intensity),
        artist_tier=artist_tier,
        primary_market=primary_market,
    )
    blended = plan.blended_cost_per_stream
    summary_rows.append(
        {
            "Scenario": label,
            "Budget ($)": budget,
            "Est. incremental streams": int(round(plan.total_incremental_streams)),
            "Cost / incremental stream ($)": (
                round(blended, 4) if blended is not None else None
            ),
        }
    )
    detail = channel_efficiency_table(plan)
    detail.insert(0, "Scenario", label)
    detail_frames.append(detail)

summary = pd.DataFrame(summary_rows)
st.subheader("Scenario summary")
st.dataframe(summary, use_container_width=True, hide_index=True)

st.subheader("Channel detail by scenario")
st.dataframe(pd.concat(detail_frames, ignore_index=True), use_container_width=True)

st.info(
    "Use **Paid Media Intelligence** for single-scenario planning with CPM overrides. "
    "Use the classic `social_lift_calculator.py` app for hourly lift curves and commerce overlays."
)

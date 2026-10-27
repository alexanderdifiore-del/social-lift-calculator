"""Paid media intelligence planner — Lollie v2."""

from datetime import datetime

import plotly.graph_objects as go
import streamlit as st

from lollie.branding import render_lollie_header
from lollie.constants import PAID_CHANNEL_DEFAULTS
from lollie.paid_media import (
    build_paid_media_plan,
    channel_efficiency_table,
    recommend_budget_shift,
)

st.set_page_config(page_title="Paid Media Intelligence | lollie", layout="wide")

render_lollie_header("paid media intelligence")

st.markdown(
    "Model how paid social spend translates into **incremental streams** "
    "using the same platform multipliers as the classic lift calculator."
)

with st.sidebar:
    st.header("Campaign")
    artist_name = st.text_input("Artist", "Example Artist")
    song_title = st.text_input("Song / Release", "Example Song")
    artist_tier = st.selectbox(
        "Artist Tier",
        ["Emerging", "Mid-tier", "Established", "Superstar"],
        index=1,
    )
    primary_market = st.selectbox(
        "Primary Market",
        ["US", "Global", "Europe", "LATAM", "APAC"],
    )
    campaign_intensity = st.slider("Campaign Intensity", 1, 10, 6)
    total_budget = st.number_input(
        "Total Paid Budget ($)",
        min_value=0.0,
        value=25000.0,
        step=500.0,
    )
    st.divider()
    st.subheader("Channel mix (%)")
    channel_weights = {}
    for channel in PAID_CHANNEL_DEFAULTS:
        channel_weights[channel] = st.slider(
            channel,
            min_value=0,
            max_value=100,
            value=25,
            help="Relative weight; values are normalized to 100% of budget.",
        )

st.caption(f"Planning for **{artist_name}** — *{song_title}*")

overrides = {}
with st.expander("Advanced CPM / CTR overrides", expanded=False):
    cols = st.columns(2)
    for idx, channel in enumerate(PAID_CHANNEL_DEFAULTS):
        defaults = PAID_CHANNEL_DEFAULTS[channel]
        with cols[idx % 2]:
            st.markdown(f"**{channel}**")
            overrides[channel] = {
                "cpm": st.number_input(
                    f"{channel} CPM ($)",
                    min_value=0.1,
                    value=float(defaults["default_cpm"]),
                    step=0.25,
                    key=f"cpm_{channel}",
                ),
                "ctr": st.number_input(
                    f"{channel} CTR",
                    min_value=0.0001,
                    max_value=0.05,
                    value=float(defaults["default_ctr"]),
                    format="%.4f",
                    key=f"ctr_{channel}",
                ),
            }

plan = build_paid_media_plan(
    total_budget_usd=total_budget,
    channel_budgets=channel_weights,
    campaign_intensity=float(campaign_intensity),
    artist_tier=artist_tier,
    primary_market=primary_market,
    channel_overrides=overrides,
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total budget", f"${plan.total_budget_usd:,.0f}")
m2.metric("Est. incremental streams", f"{plan.total_incremental_streams:,.0f}")
blended = plan.blended_cost_per_stream
m3.metric(
    "Blended cost / incremental stream",
    f"${blended:,.3f}" if blended is not None else "—",
)
m4.metric("Channels modeled", len(plan.channels))

table = channel_efficiency_table(plan)
st.subheader("Channel efficiency")
st.dataframe(table, use_container_width=True, hide_index=True)

recs = recommend_budget_shift(plan)
if not recs.empty:
    st.subheader("Budget shift suggestions")
    st.dataframe(recs, use_container_width=True, hide_index=True)

fig = go.Figure(
    data=[
        go.Bar(
            name="Budget",
            x=table["Channel"],
            y=table["Budget ($)"],
            marker_color="#00a8b8",
        ),
        go.Bar(
            name="Est. incremental streams",
            x=table["Channel"],
            y=table["Est. Incremental Streams"],
            marker_color="#008a99",
            yaxis="y2",
        ),
    ]
)
fig.update_layout(
    title="Spend vs modeled incremental streams by channel",
    barmode="group",
    yaxis=dict(title="Budget ($)"),
    yaxis2=dict(title="Streams", overlaying="y", side="right"),
    legend=dict(orientation="h"),
    height=420,
)
st.plotly_chart(fig, use_container_width=True)

st.caption(
    f"Prototype forecast generated {datetime.now():%Y-%m-%d %H:%M}. "
    "Figures are directional for planning, not guaranteed delivery."
)

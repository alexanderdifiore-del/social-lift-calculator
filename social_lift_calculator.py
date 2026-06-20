import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.markdown(
    """
    <style>
    .lollie-title {
        font-size: 4.4rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        color: #8ffcff;
        margin-bottom: 0.1rem;
        text-shadow:
            0 0 8px rgba(143, 252, 255, 0.8),
            0 0 18px rgba(143, 252, 255, 0.45),
            0 0 32px rgba(143, 252, 255, 0.25);
        font-family: "Helvetica Neue", Arial, sans-serif;
    }

    .lollie-subtitle {
        font-size: 0.95rem;
        color: rgba(255, 255, 255, 0.62);
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-top: -0.4rem;
        margin-bottom: 2rem;
    }
    </style>

    <div class="lollie-title">lollie</div>
    <div class="lollie-subtitle">social streaming lift intelligence</div>
    """,
    unsafe_allow_html=True
)

# -----------------------------
# SIDEBAR INPUTS
# -----------------------------

st.sidebar.title("Campaign Inputs")

artist_name = st.sidebar.text_input("Artist Name", "Example Artist")
song_title = st.sidebar.text_input("Song Title", "Example Song")

st.sidebar.markdown("---")
st.sidebar.subheader("Mock Opus / Track Info")

opus_campaign_id = st.sidebar.text_input("Opus Campaign ID", "OPUS-DEMO-001")
isrc = st.sidebar.text_input("ISRC", "USAT00000000")
release_phase = st.sidebar.selectbox(
    "Release Phase",
    ["Pre-release", "Release week", "Catalog/reactivation", "Tour moment", "Sync/viral moment"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("Social Post Event")

platform = st.sidebar.selectbox(
    "Platform",
    ["TikTok", "Instagram Reels", "YouTube Shorts"]
)

post_type = st.sidebar.selectbox(
    "Post Type",
    ["Organic artist post", "Influencer post", "Paid boost", "UGC trend"]
)

post_date = st.sidebar.date_input("Post Date", datetime.now().date())

post_hour = st.sidebar.slider(
    "Post Hour of Day",
    min_value=0,
    max_value=23,
    value=18,
    help="This is the clock hour when the post went live. Example: 18 = 6 PM, 23 = 11 PM."
)

post_timestamp = datetime.combine(post_date, datetime.min.time()) + timedelta(hours=post_hour)

impact_window_hours = st.sidebar.slider(
    "Impact Window Length",
    min_value=6,
    max_value=168,
    value=24,
    step=6,
    help="How many hours after the social post you want to measure lift."
)

multi_post = st.sidebar.checkbox("Simulate Second Post", False)

if multi_post:
    second_post_delay = st.sidebar.slider(
        "Second Post Delay After First Post",
        min_value=6,
        max_value=168,
        value=48,
        step=6
    )

st.sidebar.markdown("---")
st.sidebar.subheader("Artist / Market Assumptions")

artist_tier = st.sidebar.selectbox(
    "Artist Tier",
    ["Emerging", "Mid-tier", "Established", "Superstar"]
)

primary_market = st.sidebar.selectbox(
    "Primary Market",
    ["US", "Global", "Europe", "LATAM", "APAC"]
)

dsp_focus = st.sidebar.selectbox(
    "DSP Focus",
    ["All DSPs", "Spotify-heavy", "Apple-heavy", "YouTube Music-heavy", "Amazon-heavy"]
)

campaign_intensity = st.sidebar.slider(
    "Campaign Intensity Score",
    min_value=1,
    max_value=10,
    value=6,
    help="Mock score representing how strong the social push is."
)

analysis_days = st.sidebar.selectbox(
    "Analysis Window",
    [7, 14, 30],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.subheader("Manual Demo Inputs")

data_mode = st.sidebar.radio(
    "Data Source Mode",
    ["Auto simulation", "Manual demo inputs"],
    help="Auto simulation generates fake hourly data. Manual demo inputs let you type fake campaign numbers yourself."
)

manual_expected_streams = st.sidebar.number_input(
    "Manual Expected Streams",
    min_value=0,
    value=65000,
    step=1000,
    help="What streams would have been without the social post."
)

manual_actual_streams = st.sidebar.number_input(
    "Manual Actual Streams",
    min_value=0,
    value=148000,
    step=1000,
    help="What streams happened after the social post."
)

manual_social_reach = st.sidebar.number_input(
    "Manual Social Reach / Views",
    min_value=0,
    value=850000,
    step=10000,
    help="Fake TikTok/Reels/Shorts views or reach number for demo purposes."
)

manual_engagement_rate = st.sidebar.slider(
    "Manual Engagement Rate (%)",
    min_value=0.0,
    max_value=25.0,
    value=5.5,
    step=0.1,
    help="Fake engagement rate for the post."
)

# -----------------------------
# MOCK DATA GENERATION
# -----------------------------

hours = analysis_days * 24
start_time = post_timestamp - timedelta(days=analysis_days // 2)

timestamps = pd.date_range(start=start_time, periods=hours, freq="h")

np.random.seed(42)

tier_multiplier = {
    "Emerging": 0.8,
    "Mid-tier": 1.4,
    "Established": 2.2,
    "Superstar": 3.5
}[artist_tier]

platform_multiplier = {
    "TikTok": 1.65,
    "Instagram Reels": 1.35,
    "YouTube Shorts": 1.45
}[platform]

market_multiplier = {
    "US": 1.25,
    "Global": 1.0,
    "Europe": 1.1,
    "LATAM": 1.2,
    "APAC": 1.15
}[primary_market]

dsp_multiplier = {
    "All DSPs": 1.0,
    "Spotify-heavy": 1.15,
    "Apple-heavy": 1.05,
    "YouTube Music-heavy": 1.1,
    "Amazon-heavy": 0.95
}[dsp_focus]

post_type_multiplier = {
    "Organic artist post": 1.15,
    "Influencer post": 1.35,
    "Paid boost": 1.25,
    "UGC trend": 1.6
}[post_type]

def daily_rhythm(hour):
    if 0 <= hour <= 5:
        return 0.55
    elif 6 <= hour <= 9:
        return 0.85
    elif 10 <= hour <= 15:
        return 1.0
    elif 16 <= hour <= 20:
        return 1.45
    else:
        return 1.2

baseline_values = []

for ts in timestamps:
    base = 2800
    base *= daily_rhythm(ts.hour)
    base *= tier_multiplier
    base *= market_multiplier
    base *= dsp_multiplier
    base += np.random.normal(0, 180)

    baseline_values.append(max(base, 500))

df = pd.DataFrame({
    "timestamp": timestamps,
    "expected_baseline_streams": baseline_values
})

df["actual_streams"] = df["expected_baseline_streams"].copy()

# -----------------------------
# SOCIAL LIFT MODEL
# -----------------------------

def apply_social_lift(dataframe, event_time, strength_multiplier=1.0):
    impact_mask = (
        (dataframe["timestamp"] >= event_time)
        &
        (dataframe["timestamp"] < event_time + timedelta(hours=impact_window_hours))
    )

    n = impact_mask.sum()

    if n == 0:
        return dataframe

    starting_lift = (
        1.4
        + campaign_intensity * 0.22
        + platform_multiplier * 0.25
        + post_type_multiplier * 0.3
    ) * strength_multiplier

    ending_lift = 1.05

    decay_curve = np.linspace(starting_lift, ending_lift, n)

    dataframe.loc[impact_mask, "actual_streams"] = (
        dataframe.loc[impact_mask, "actual_streams"].values * decay_curve
    )

    return dataframe

df = apply_social_lift(df, post_timestamp, 1.0)

if multi_post:
    second_post_timestamp = post_timestamp + timedelta(hours=second_post_delay)
    df = apply_social_lift(df, second_post_timestamp, 0.65)

# -----------------------------
# METRICS
# -----------------------------

impact_end = post_timestamp + timedelta(hours=impact_window_hours)

impact_mask = (
    (df["timestamp"] >= post_timestamp)
    &
    (df["timestamp"] < impact_end)
)

expected_streams = df.loc[impact_mask, "expected_baseline_streams"].sum()
actual_streams = df.loc[impact_mask, "actual_streams"].sum()
social_lift_streams = actual_streams - expected_streams
lift_percent = (social_lift_streams / expected_streams) * 100

hourly_baseline_rate = df["expected_baseline_streams"].mean()

df["lift_area"] = df["actual_streams"] - df["expected_baseline_streams"]
df.loc[df["lift_area"] < 0, "lift_area"] = 0

# Manual demo override:
# If selected, these sidebar numbers replace the simulated impact-window totals.
if data_mode == "Manual demo inputs":
    current_expected_total = df.loc[impact_mask, "expected_baseline_streams"].sum()
    current_actual_total = df.loc[impact_mask, "actual_streams"].sum()

    if current_expected_total > 0:
        df.loc[impact_mask, "expected_baseline_streams"] *= (
            manual_expected_streams / current_expected_total
        )

    if current_actual_total > 0:
        df.loc[impact_mask, "actual_streams"] *= (
            manual_actual_streams / current_actual_total
        )

    expected_streams = df.loc[impact_mask, "expected_baseline_streams"].sum()
    actual_streams = df.loc[impact_mask, "actual_streams"].sum()
    social_lift_streams = actual_streams - expected_streams

    if expected_streams > 0:
        lift_percent = (social_lift_streams / expected_streams) * 100
    else:
        lift_percent = 0

    hourly_baseline_rate = expected_streams / impact_window_hours

    df["lift_area"] = df["actual_streams"] - df["expected_baseline_streams"]
    df.loc[df["lift_area"] < 0, "lift_area"] = 0

# -----------------------------
# MAIN PAGE
# -----------------------------

st.markdown(
    """
    <div style="
        font-size: 1.35rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: rgba(143, 252, 255, 0.82);
        text-shadow:
            0 0 6px rgba(143, 252, 255, 0.35),
            0 0 14px rgba(143, 252, 255, 0.18);
        font-family: 'Helvetica Neue', Arial, sans-serif;
        margin-top: 0.75rem;
        margin-bottom: 1.5rem;
    ">
        Social Media Streaming Lift Calculator
    </div>
    """,
    unsafe_allow_html=True
)

st.subheader(f"{artist_name} — {song_title}")

st.caption(
    f"Campaign: {opus_campaign_id} | ISRC: {isrc} | Platform: {platform} | Market: {primary_market}"
)

st.info(
    f"""
    **Social post time:** {post_timestamp.strftime('%B %d, %Y at %I:%M %p')}

    The post hour is the clock hour when the post went live.
    For example, hour **23** means **11:00 PM** on the selected post date.
    """
)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Hourly Baseline Rate", f"{hourly_baseline_rate:,.0f}")
col2.metric(f"Actual Streams ({impact_window_hours}h)", f"{actual_streams:,.0f}")
col3.metric(f"Expected Streams ({impact_window_hours}h)", f"{expected_streams:,.0f}")
col4.metric("Estimated Social Lift", f"{social_lift_streams:,.0f}", f"{lift_percent:,.1f}%")

st.markdown("### Impact Window Summary")

summary_df = pd.DataFrame({
    "Metric": [
        "Expected Baseline",
        "Actual Streams",
        "Estimated Social Lift"
    ],
    "Streams": [
        expected_streams,
        actual_streams,
        social_lift_streams
    ]
})

bar_fig = go.Figure()

bar_fig.add_trace(go.Bar(
    x=summary_df["Metric"],
    y=summary_df["Streams"],
    text=[f"{x:,.0f}" for x in summary_df["Streams"]],
    textposition="outside",
    marker=dict(
        color=[
            "rgba(143, 252, 255, 0.45)",
            "rgba(143, 252, 255, 0.90)",
            "rgba(88, 255, 166, 0.85)"
        ],
        line=dict(
            color="rgba(255,255,255,0.35)",
            width=1
        )
    )
))

bar_fig.update_layout(
    title="Campaign Performance Summary",
    xaxis_title="Metric",
    yaxis_title="Streams",
    template="plotly_dark",
    height=420,
    margin=dict(l=40, r=40, t=70, b=40),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(
        family="Helvetica Neue, Arial, sans-serif",
        color="rgba(255,255,255,0.86)"
    )
)

st.plotly_chart(bar_fig, use_container_width=True)

if data_mode == "Manual demo inputs":
    st.caption(
        f"Manual demo mode active: reach/views set to {manual_social_reach:,.0f} "
        f"with {manual_engagement_rate:.1f}% engagement."
    )
else:
    st.caption("Auto simulation mode active: values are generated from the model assumptions.")

# -----------------------------
# CHART
# -----------------------------

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df["timestamp"],
    y=df["expected_baseline_streams"],
    mode="lines",
    name="Expected Baseline Streams",
    line=dict(width=2),
    hovertemplate="Time: %{x}<br>Expected: %{y:,.0f}<extra></extra>"
))

fig.add_trace(go.Scatter(
    x=df["timestamp"],
    y=df["actual_streams"],
    mode="lines",
    name="Actual Streams",
    line=dict(width=3),
    hovertemplate="Time: %{x}<br>Actual: %{y:,.0f}<extra></extra>"
))

lift_df = df.loc[impact_mask]

fig.add_trace(go.Scatter(
    x=pd.concat([lift_df["timestamp"], lift_df["timestamp"][::-1]]),
    y=pd.concat([lift_df["actual_streams"], lift_df["expected_baseline_streams"][::-1]]),
    fill="toself",
    name="Estimated Social Lift Area",
    opacity=0.25,
    line=dict(width=0),
    hoverinfo="skip"
))

fig.add_vline(
    x=post_timestamp,
    line_width=2,
    line_dash="dash",
    annotation_text="Social Post Goes Live",
    annotation_position="top"
)

fig.add_vrect(
    x0=post_timestamp,
    x1=impact_end,
    fillcolor="gray",
    opacity=0.08,
    line_width=0,
    annotation_text=f"{impact_window_hours}h Impact Window",
    annotation_position="top left"
)

if multi_post:
    fig.add_vline(
        x=second_post_timestamp,
        line_width=2,
        line_dash="dot",
        annotation_text="Second Post",
        annotation_position="top"
    )

fig.update_layout(
    title=f"{song_title} Streaming Trend: Expected vs Actual",
    xaxis_title="Date / Time",
    yaxis_title="Hourly Streams",
    legend_title="Chart Labels",
    hovermode="x unified",
    template="plotly_white",
    height=675,
    margin=dict(l=40, r=40, t=80, b=40)
)

st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# EXPLANATION
# -----------------------------

st.markdown("""
### How to read this dashboard

**Data Source Mode**  
The dashboard can run in two modes:

- **Auto simulation** generates mock hourly streaming data using the sidebar assumptions.
- **Manual demo inputs** lets you type fake campaign numbers directly into the sidebar so the KPIs, lift estimate, and summary bar chart update during a demo.

**Expected Baseline Streams**  
The model’s estimate of how many streams the track would have received without the social post.

**Actual Streams**  
The simulated or manually entered stream count after the social post goes live.

**Estimated Social Lift**  
The difference between actual streams and expected baseline streams.

**Formula**  
Estimated Social Lift = Actual Streams - Expected Baseline Streams

**Impact Window**  
The selected measurement period after the post. A 24-hour window is useful for fast TikTok/Reels/Shorts spikes. A 72-hour or 168-hour window is better for slower campaign effects.

**Impact Window Summary**  
The bar chart compares expected streams, actual streams, and estimated lift so the campaign impact is easy to read at a glance.

**Important note**  
This is a prototype using mock or manually entered demo data. It is designed to show the logic and workflow of a music analytics tool, not to represent real Opus, DSP, or confidential label data.




Conceptualized and designed by Alexander DiFiore, Rhino. Named "lollie" after his two beloved cats, Lily and Ollie.

""")

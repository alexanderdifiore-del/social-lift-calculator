"""lollie: paid advertising + organic social -> streaming performance -> commerce revenue.

One dashboard. Production mode (the default) uses only data you upload or type in.
Simulated data is available only when Demo mode is switched on in the sidebar's
"Advanced / Demo" section.
"""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from lollie.branding import render_lollie_header, render_section_title
from lollie.commerce import build_commerce_model, build_commerce_overlay
from lollie.constants import (
    ARTIST_TIER_MULTIPLIER,
    DSP_MULTIPLIER,
    MARKET_MULTIPLIER,
    PLATFORM_MULTIPLIER,
    POST_TYPE_MULTIPLIER,
)
from lollie.paid.demo import synthetic_paid_media
from lollie.paid.metrics import Thresholds, as_of_default, campaign_market_table
from lollie.paid.report import build_recap
from lollie.paid.timeseries import daily_series, flights, overlap_report
from lollie.streaming import (
    apply_social_lift,
    granularity_label,
    impact_window_mask,
    manual_summary,
    simulate_baseline,
    summarize_impact,
)
from lollie.ui import charts
from lollie.ui.commerce_inputs import render_commerce_sidebar
from lollie.ui.credits_section import render_credits_compact
from lollie.ui.paid_sections import (
    PaidData,
    UPLOAD_TYPES,
    ingest_uploaded_files,
    link_campaigns,
    money,
    number,
    pick_currency,
    render_audience_creative,
    render_kpis,
    render_market_table,
    render_results,
    show_issues,
)
from lollie.ui.streaming_import import render_streaming_import

st.set_page_config(page_title="lollie", page_icon="🍭", layout="wide")

render_lollie_header("paid media • streaming • commerce intelligence")

# The Demo toggle lives at the bottom of the sidebar but is needed here first;
# Streamlit has already stored its value before the script runs.
demo_mode = bool(st.session_state.get("lollie_demo_mode", False))

# -----------------------------
# SIDEBAR INPUTS
# -----------------------------

st.sidebar.title("Campaign Inputs")

artist_name = st.sidebar.text_input("Artist Name", "Example Artist")
song_title = st.sidebar.text_input("Song Title", "Example Song")

st.sidebar.markdown("---")
st.sidebar.subheader("Opus / Track Info")

opus_campaign_id = st.sidebar.text_input("Opus Campaign ID", "OPUS-DEMO-001")
isrc = st.sidebar.text_input("ISRC", "USAT00000000")
release_phase = st.sidebar.selectbox(
    "Release Phase",
    ["Pre-release", "Release week", "Catalog/reactivation", "Tour moment", "Sync/viral moment"],
)

st.sidebar.markdown("---")
st.sidebar.subheader("Social Post Event")

platform = st.sidebar.selectbox(
    "Platform",
    [
        "TikTok",
        "Instagram Reels",
        "YouTube Shorts",
        "YouTube Video",
        "YouTube Visualizer",
        "YouTube Music Video",
        "YouTube Live Performance",
        "Snapchat",
    ],
)

post_type = st.sidebar.selectbox(
    "Post Type",
    ["Organic artist post", "Influencer post", "Paid boost", "UGC trend"],
)

post_date = st.sidebar.date_input("Post Date", datetime.now().date())

post_hour = st.sidebar.slider(
    "Post Hour of Day",
    min_value=0,
    max_value=23,
    value=18,
    help="This is the clock hour when the post went live. Example: 18 = 6 PM, 23 = 11 PM.",
)

post_timestamp = datetime.combine(post_date, datetime.min.time()) + timedelta(hours=post_hour)

impact_window_hours = st.sidebar.slider(
    "Impact Window Length",
    min_value=6,
    max_value=168,
    value=24,
    step=6,
    help="How many hours after the social post you want to measure lift.",
)

multi_post = st.sidebar.checkbox(
    "Simulate Second Post" if demo_mode else "Mark a Second Post",
    False,
    help="Adds a second post to the chart."
    + (" In Demo mode it also adds a smaller simulated lift." if demo_mode else " It is a marker only; your data is not changed."),
)
second_post_delay = 48
if multi_post:
    second_post_delay = st.sidebar.slider(
        "Second Post Delay After First Post", min_value=6, max_value=168, value=48, step=6
    )

with st.sidebar.expander("More organic posts to mark on the chart"):
    extra_posts_text = st.text_area(
        "One per line: date time, label",
        value="",
        placeholder="2026-10-21 18:00, Instagram Reel",
        help="Adds a dotted marker to the streaming chart. Nothing else is changed.",
        key="extra_posts_text",
    )

st.sidebar.markdown("---")
st.sidebar.subheader("Artist / Market Assumptions")

primary_market = st.sidebar.selectbox("Primary Market", ["US", "Global", "Europe", "LATAM", "APAC"])
dsp_focus = st.sidebar.selectbox(
    "DSP Focus",
    ["All DSPs", "Spotify-heavy", "Apple-heavy", "YouTube Music-heavy", "Amazon-heavy"],
)
analysis_days = st.sidebar.selectbox(
    "Analysis Window",
    [7, 14, 30],
    index=0,
    help="Length of the simulated timeline in Demo mode. Uploaded data uses its own date range.",
)

st.sidebar.markdown("---")
st.sidebar.subheader("Streaming Data")

if demo_mode:
    data_mode = st.sidebar.radio(
        "Data Source Mode",
        ["Auto simulation", "Manual demo inputs", "CSV upload"],
        help="Choose whether the dashboard uses simulated data, manual demo numbers, or an uploaded file.",
    )
else:
    data_mode = st.sidebar.radio(
        "Data Source Mode",
        ["CSV / Excel upload", "Manual entry"],
        help="Upload hourly or daily streaming data, or type the expected and actual totals for the impact window.",
    )

uploaded_streaming = None
if data_mode in ("CSV upload", "CSV / Excel upload"):
    uploaded_streaming = st.sidebar.file_uploader(
        "Upload Streaming File",
        type=UPLOAD_TYPES,
        key="streaming_upload",
        help="A CSV or Excel file with a timestamp and actual_streams column. expected_baseline_streams is optional.",
    )
    with st.sidebar.expander("File format example"):
        st.code(
            """timestamp,actual_streams,expected_baseline_streams
2026-06-17 00:00:00,2400,2300
2026-06-17 01:00:00,2100,2200
2026-06-17 02:00:00,1900,2100""",
            language="csv",
        )

mode_suffix = "demo" if demo_mode else "live"
manual_expected_streams = manual_actual_streams = 0
if data_mode in ("Manual demo inputs", "Manual entry"):
    manual_expected_streams = st.sidebar.number_input(
        "Manual Expected Streams",
        min_value=0,
        value=65000 if demo_mode else 0,
        step=1000,
        key=f"manual_expected_{mode_suffix}",
        help="What streams would have been without the social post.",
    )
    manual_actual_streams = st.sidebar.number_input(
        "Manual Actual Streams",
        min_value=0,
        value=148000 if demo_mode else 0,
        step=1000,
        key=f"manual_actual_{mode_suffix}",
        help="What streams happened after the social post.",
    )

manual_social_reach = st.sidebar.number_input(
    "Social Reach / Views",
    min_value=0,
    value=850000 if demo_mode else 0,
    step=10000,
    key=f"social_reach_{mode_suffix}",
    help="Views or reach of the organic social post. Used for revenue per 1K social views.",
)
manual_engagement_rate = st.sidebar.slider(
    "Engagement Rate (%)",
    min_value=0.0,
    max_value=25.0,
    value=5.5 if demo_mode else 0.0,
    step=0.1,
    key=f"engagement_{mode_suffix}",
    help="Engagement rate of the organic social post, if known.",
)

st.sidebar.markdown("---")
st.sidebar.subheader("Paid Media Data")

paid_files = []
paid_default_currency = "USD"
if demo_mode:
    st.sidebar.caption("Demo mode is on: synthetic paid media is shown. Uploaded files are ignored until Demo mode is turned off.")
else:
    paid_files = st.sidebar.file_uploader(
        "Upload Paid Media Reports",
        type=UPLOAD_TYPES,
        accept_multiple_files=True,
        key="paid_uploads",
        help="Exports from Meta, TikTok, Google Ads / YouTube, Snapchat, WAVO or similar. CSV or Excel.",
    )
    paid_default_currency = st.sidebar.selectbox(
        "Currency if a file does not say",
        ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "MXN", "BRL"],
        help="Used only when a file has no currency column or currency in the spend heading.",
    )
sidebar_campaign_link = st.sidebar.container()

inputs = render_commerce_sidebar(
    demo_mode=demo_mode,
    post_timestamp=post_timestamp,
    social_reach=float(manual_social_reach),
)

st.sidebar.markdown("---")
with st.sidebar.expander("Advanced / Demo", expanded=demo_mode):
    st.toggle(
        "Demo mode (simulated data)",
        key="lollie_demo_mode",
        help="Shows clearly labeled simulated streaming, paid media and commerce data for training. "
        "It is never mixed with real data.",
    )
    st.caption("Demo mode is for training only. Turn it off to work with real data.")
    artist_tier = st.selectbox("Artist Tier", list(ARTIST_TIER_MULTIPLIER), key="adv_tier",
                               help="Used only to size the simulated streaming baseline in Demo mode.")
    campaign_intensity = st.slider(
        "Campaign Intensity Score", min_value=1, max_value=10, value=6, key="adv_intensity",
        help="Mock score for how strong the social push is. Used only by the Demo simulation.",
    )
    st.markdown("**Goal status thresholds**")
    ahead_pct = st.slider("Ahead of goal at (% of goal)", 100, 150, 110, 5, key="adv_ahead")
    on_track_pct = st.slider("On track at (% of goal)", 50, 100, 90, 5, key="adv_on_track")
thresholds = Thresholds(ahead=ahead_pct / 100, on_track=on_track_pct / 100)

# -----------------------------
# PAGE SKELETON (sections fill in below)
# -----------------------------

render_section_title("Campaign Intelligence Dashboard")
banner_box = st.container()
box_a = st.container()
box_b = st.container()
box_c = st.container()
box_d = st.container()
box_e = st.container()
box_f = st.container()
box_recap = st.container()
box_help = st.container()

flags: list[tuple[str, str]] = []

if demo_mode:
    with banner_box:
        st.warning(
            "**DEMO MODE.** Everything below is simulated for training and is not real campaign data. "
            "Turn off Demo mode in the sidebar (Advanced / Demo) to see only your own data."
        )

# -----------------------------
# PAID MEDIA DATA (section B import)
# -----------------------------

with box_b:
    st.markdown("---")
    render_section_title("B · Paid Media Performance")
    paid_import_box = st.container()

if demo_mode:
    demo_result = synthetic_paid_media(pd.Timestamp(post_timestamp))
    paid = PaidData(frame=demo_result.frame, issues=[], results=[demo_result], is_demo=True)
elif paid_files:
    paid = ingest_uploaded_files(list(paid_files), paid_default_currency, paid_import_box)
else:
    paid = PaidData()

paid_frame = paid.frame
paid_view = pd.DataFrame()
paid_currency = "USD"
if not paid_frame.empty:
    paid_view = link_campaigns(paid_frame, artist_name, sidebar_campaign_link)

# -----------------------------
# STREAMING DATA (section C import)
# -----------------------------

with box_c:
    st.markdown("---")
    render_section_title("C · Streaming Impact Analysis")
    stream_import_box = st.container()

stream_df = None
granularity = "intraday"
summary = None
stream_source_caption = ""
paid_estimated_note = ""
manual_only = False
extra_posts: list[tuple[datetime, str]] = []
second_post_timestamp = None

if multi_post:
    second_post_timestamp = post_timestamp + timedelta(hours=second_post_delay)
    extra_posts.append((second_post_timestamp, "Second Post"))
for line in extra_posts_text.splitlines():
    if not line.strip():
        continue
    stamp, _, label = line.partition(",")
    parsed = pd.to_datetime(stamp.strip(), errors="coerce")
    if pd.isna(parsed):
        flags.append(("warning", f"Could not read the post time '{stamp.strip()}'. Use a format like 2026-10-21 18:00."))
        continue
    extra_posts.append((parsed.to_pydatetime(), label.strip() or "Organic post"))

if demo_mode and data_mode == "Auto simulation" or (demo_mode and data_mode == "CSV upload" and uploaded_streaming is None):
    stream_df = simulate_baseline(
        post_timestamp,
        analysis_days,
        tier_multiplier=ARTIST_TIER_MULTIPLIER[artist_tier],
        market_multiplier=MARKET_MULTIPLIER[primary_market],
        dsp_multiplier=DSP_MULTIPLIER[dsp_focus],
    )
    stream_df = apply_social_lift(
        stream_df,
        post_timestamp,
        impact_window_hours,
        campaign_intensity=campaign_intensity,
        platform_multiplier=PLATFORM_MULTIPLIER[platform],
        post_type_multiplier=POST_TYPE_MULTIPLIER[post_type],
    )
    if multi_post:
        stream_df = apply_social_lift(
            stream_df,
            second_post_timestamp,
            impact_window_hours,
            campaign_intensity=campaign_intensity,
            platform_multiplier=PLATFORM_MULTIPLIER[platform],
            post_type_multiplier=POST_TYPE_MULTIPLIER[post_type],
            strength_multiplier=0.65,
        )
    stream_source_caption = "Auto simulation mode active: values are generated from the model assumptions (demo data)."
    if data_mode == "CSV upload":
        stream_source_caption = "CSV upload mode selected, but no file has been uploaded yet. Showing simulated data."
elif data_mode in ("Manual demo inputs", "Manual entry"):
    manual_only = True
    summary = manual_summary(manual_expected_streams, manual_actual_streams)
    stream_source_caption = (
        f"Manual entry mode active: expected and actual totals were typed in. Reach/views {manual_social_reach:,.0f}"
        f" with {manual_engagement_rate:.1f}% engagement."
    )
elif uploaded_streaming is not None:
    prep = render_streaming_import(
        uploaded_streaming,
        stream_import_box,
        post_timestamp=post_timestamp,
        impact_window_hours=impact_window_hours,
    )
    if prep is not None:
        stream_df = prep.frame
        granularity = prep.granularity
        for note in prep.notes:
            flags.append(("info", note))
        stream_source_caption = "File upload mode active: the dashboard is using your uploaded streaming data."

if stream_df is not None and not manual_only:
    mask = impact_window_mask(stream_df["timestamp"], post_timestamp, impact_window_hours, granularity)
    if mask.any():
        summary = summarize_impact(stream_df, mask)
    else:
        flags.append(
            (
                "warning",
                "No streaming rows fall inside the impact window. Check the post date and hour against the streaming data dates.",
            )
        )
    stream_mask = mask
else:
    stream_mask = None

social_lift_streams = summary.lift if summary else 0.0

# -----------------------------
# COMMERCE MODEL
# -----------------------------

commerce_model = build_commerce_model(inputs.rows, float(manual_social_reach), social_lift_streams) if inputs.enabled else None
commerce_has_data = bool(commerce_model) and not commerce_model.is_empty and (
    commerce_model.gross_revenue > 0 or commerce_model.units > 0
)

# -----------------------------
# SECTION B: PAID MEDIA PERFORMANCE
# -----------------------------

as_of = pd.Timestamp.today().normalize()
kpis: dict = {}
market_view = pd.DataFrame()
best: dict = {}
paid_daily = pd.DataFrame()
paid_flights = pd.DataFrame()

with box_b:
    if paid.is_demo:
        st.caption("Synthetic demo paid media (Demo mode).")
    show_issues(paid.issues)

    if paid_view.empty:
        if paid_files and not paid_frame.empty:
            st.info("No paid campaigns are linked to this release. Pick campaigns in the sidebar under Paid Media Data.")
        elif paid_files:
            st.warning("The uploaded paid media files had no usable rows yet. Check the import settings above.")
        else:
            st.info(
                "No paid media data loaded yet. Upload exports from Meta, TikTok, Google Ads / YouTube, Snapchat or WAVO "
                "in the sidebar under Paid Media Data. Organic streaming and commerce analysis below still work without it."
            )
    else:
        paid_currency = pick_currency(paid_view)
        paid_view = paid_view[paid_view["currency"] == paid_currency].reset_index(drop=True)
        as_of = as_of_default(paid_view)
        st.caption(
            f"Showing {paid_view['campaign_name'].nunique()} linked campaign(s) in {paid_currency}, "
            f"data through {as_of:%B %d, %Y}. Budget is counted once per campaign and market."
        )
        kpis = render_kpis(paid_view, paid_currency, as_of)
        st.markdown("#### Results")
        render_results(paid_view, paid_currency)
        st.markdown("#### Performance by Market")
        market_view = render_market_table(paid_view, as_of, thresholds)
        paid_daily = daily_series(paid_view)
        paid_flights = flights(paid_view)
        if paid_view["source_file"].nunique() > 1:
            st.caption("Sources: " + ", ".join(sorted(paid_view["source_file"].dropna().unique())))
        if paid_daily.empty:
            flags.append(("warning", "The paid media files have no usable dates, so spend cannot be placed on the streaming timeline."))
        else:
            stream_stamps = stream_df["timestamp"] if stream_df is not None else None
            for note in overlap_report(paid_daily, stream_stamps):
                flags.append(("warning" if "do not overlap" in note or "missing" in note else "info", note))

# -----------------------------
# SECTION C: STREAMING IMPACT ANALYSIS
# -----------------------------

with box_c:
    if summary is None and stream_df is None and not manual_only:
        st.info(
            "No streaming data loaded yet. Upload a CSV or Excel file in the sidebar (Streaming Data), or switch to "
            "Manual entry to type in expected and actual totals."
        )
    elif summary is not None:
        unit_noun = "Daily" if granularity == "daily" else "Hourly"
        col1, col2, col3, col4 = st.columns(4)
        if manual_only:
            col1.metric(f"{unit_noun} Baseline Rate", "n/a")
        else:
            col1.metric(f"{unit_noun} Baseline Rate", f"{summary.baseline_rate:,.0f}")
        col2.metric(f"Actual Streams ({impact_window_hours}h)", f"{summary.actual:,.0f}")
        col3.metric(f"Expected Streams ({impact_window_hours}h)", f"{summary.expected:,.0f}")
        col4.metric(
            "Estimated Social Lift",
            f"{summary.lift:,.0f}",
            f"{summary.lift_percent:,.1f}%" if summary.lift_percent is not None else None,
        )
        st.caption(
            "Estimated Social Lift is an observational, modeled estimate (actual streams minus an expected baseline). "
            "It does not prove that the post or any advertising caused the difference."
        )
        if granularity == "daily":
            st.caption("This file has one row per day, so the impact window is measured in whole days starting on the post date.")

        st.markdown("### Impact Window Summary")
        st.plotly_chart(charts.summary_bar_chart(summary.expected, summary.actual, summary.lift), width="stretch")
        if stream_source_caption:
            st.caption(stream_source_caption)

        if paid_daily is not None and not paid_daily.empty and stream_df is not None and stream_mask is not None:
            window_days = max(int(-(-impact_window_hours // 24)), 1)
            post_day = pd.Timestamp(post_timestamp).normalize()
            in_window = paid_daily[(paid_daily["date"] >= post_day) & (paid_daily["date"] < post_day + pd.Timedelta(days=window_days))]
            st.markdown("#### Paid media during the impact window")
            if in_window.empty:
                st.caption("No paid media delivery is recorded in this impact window.")
            else:
                w1, w2, w3 = st.columns(3)
                w1.metric("Paid spend in window", money(in_window["spend"].sum(min_count=1), paid_currency))
                w2.metric("Paid impressions in window", number(in_window["impressions"].sum(min_count=1)))
                w3.metric("Days with paid delivery", f"{len(in_window)} of {window_days}")

        if stream_df is not None and not manual_only:
            overlay_cols = st.columns(3)
            show_paid_overlay = overlay_cols[0].checkbox(
                "Show paid flights and daily spend", value=True, disabled=paid_daily.empty, key="show_paid_overlay"
            )
            show_posts = overlay_cols[1].checkbox("Show organic post markers", value=True, key="show_posts")
            overlay_cols[2].caption("Commerce overlay is controlled in the sidebar.")

            commerce_overlay = None
            if inputs.enabled and inputs.show_overlay and commerce_has_data:
                commerce_overlay = build_commerce_overlay(
                    commerce_model,
                    inputs.overlay_metric,
                    post_timestamp,
                    inputs.overlay_window_days,
                    stream_df["timestamp"].min(),
                    allow_projection=inputs.is_estimate,
                )
                if commerce_overlay.is_empty:
                    flags.append(
                        (
                            "info",
                            "No dated sales fall in the commerce overlay window, so no commerce line is drawn on the streaming chart.",
                        )
                    )

            impact_end = post_timestamp + timedelta(hours=impact_window_hours)
            figure = charts.streaming_chart(
                df=stream_df,
                impact_mask=stream_mask,
                granularity=granularity,
                post_timestamp=post_timestamp,
                impact_end=impact_end,
                impact_window_hours=impact_window_hours,
                song_title=song_title,
                extra_posts=extra_posts if show_posts else [],
                commerce=commerce_overlay,
                show_commerce_baseline=inputs.show_baseline,
                commerce_baseline_percent=inputs.baseline_percent,
                paid_daily=paid_daily if show_paid_overlay else None,
                paid_flights=paid_flights if show_paid_overlay else None,
                paid_currency=paid_currency,
            )
            st.plotly_chart(figure, width="stretch")
            st.caption(
                f"{granularity_label(granularity)} are shown at the detail the file provides; daily data is never turned into hourly data. "
                "The shaded lift area and the baseline are modeled, observational estimates."
            )
        elif manual_only:
            st.info("Manual entry has totals only, so there is no timeline chart. Upload hourly or daily data to see the streaming trend with paid and commerce overlays.")

# -----------------------------
# SECTION D: AUDIENCE & CREATIVE PERFORMANCE
# -----------------------------

with box_d:
    st.markdown("---")
    render_section_title("D · Audience & Creative Performance")
    if paid_view.empty:
        st.info("Load paid media data (with ad set / ad group and ad names) to compare audiences and creatives.")
    else:
        best = render_audience_creative(paid_view, paid_currency)

# -----------------------------
# SECTION E: COMMERCE REVENUE
# -----------------------------

with box_e:
    st.markdown("---")
    render_section_title("E · Commerce Revenue")
    if not inputs.enabled:
        st.info("Commerce revenue tracking is currently off. Enable it in the sidebar to track merch, physical product, and other campaign-related sales.")
    elif not commerce_has_data:
        for message in inputs.messages:
            st.warning(message)
        st.info(
            "No commerce data yet. Upload a sales file or type dated sales in the sidebar under Commerce / Product Revenue."
        )
    else:
        st.markdown("### Commerce Revenue Attribution")
        revenue_col1, revenue_col2, revenue_col3, revenue_col4 = st.columns(4)
        revenue_col1.metric("Attributed Product Revenue", f"${commerce_model.gross_revenue:,.0f}")
        revenue_col2.metric("Estimated Net Revenue", f"${commerce_model.net_revenue:,.0f}")
        revenue_col3.metric("Attributed Units Sold", f"{commerce_model.units:,.0f}")
        revenue_col4.metric(
            "Revenue per 1K Social Views",
            f"${commerce_model.revenue_per_1k_social_views:,.2f}" if manual_social_reach > 0 else "n/a",
            help="Needs social reach / views in the sidebar." if manual_social_reach <= 0 else None,
        )

        st.plotly_chart(charts.commerce_bar_chart(commerce_model.by_product), width="stretch")

        money_columns = [
            "Average Selling Price",
            "Unit Cost / COGS",
            "Gross Revenue",
            "Total COGS",
            "Fees / Discounts",
            "Estimated Net Revenue",
        ]
        display_product_df = commerce_model.by_product.copy()
        for column in money_columns:
            display_product_df[column] = display_product_df[column].map(lambda value: f"${value:,.2f}")
        display_product_df["Estimated Margin (%)"] = display_product_df["Estimated Margin (%)"].map(lambda value: f"{value:,.1f}%")
        st.dataframe(display_product_df, width="stretch", hide_index=True)

        st.markdown("#### Dated Product Sales Detail")
        display_detail_df = commerce_model.detail.copy()
        display_detail_df["Sale Date"] = display_detail_df["Sale Date"].dt.strftime("%Y-%m-%d")
        for column in money_columns:
            display_detail_df[column] = display_detail_df[column].map(lambda value: f"${value:,.2f}")
        display_detail_df["Estimated Margin (%)"] = display_detail_df["Estimated Margin (%)"].map(lambda value: f"{value:,.1f}%")
        st.dataframe(display_detail_df, width="stretch", hide_index=True)

        if commerce_model.revenue_per_lift_stream > 0:
            lift_text = f" Revenue per lift stream is approximately ${commerce_model.revenue_per_lift_stream:,.2f}."
        else:
            lift_text = " Revenue per lift stream is not available without a positive streaming lift."
        source_text = "Commerce estimate (demo)" if inputs.is_estimate else "Commerce data loaded"
        commerce_note = (
            f"{source_text}: ${commerce_model.gross_revenue:,.0f} in attributed gross product revenue and "
            f"${commerce_model.net_revenue:,.0f} in estimated net revenue.{lift_text} "
            "Revenue is shown next to the streaming window for context and is not proof the post or ads caused the sales."
        )
        st.caption(commerce_note.replace("$", "\\$"))

# -----------------------------
# SECTION F: AD CREDITS & FUNDING
# -----------------------------

with box_f:
    st.markdown("---")
    render_section_title("F · Ad Credits & Funding")
    render_credits_compact(demo_mode, artist=artist_name, campaign=opus_campaign_id)

# -----------------------------
# SECTION A: CAMPAIGN OVERVIEW (filled last, shown first)
# -----------------------------

with box_a:
    render_section_title("A · Campaign Overview")
    st.subheader(f"{artist_name} — {song_title}")
    st.caption(
        f"Campaign: {opus_campaign_id} | ISRC: {isrc} | Release phase: {release_phase} | "
        f"Platform: {platform} | Market: {primary_market} | DSP focus: {dsp_focus}"
    )
    st.info(
        f"""
        **Social post time:** {post_timestamp.strftime('%B %d, %Y at %I:%M %p')}

        The post hour is the clock hour when the post went live.
        For example, hour **23** means **11:00 PM** on the selected post date.
        """
    )
    st.caption("Paid advertising and organic social  →  streaming performance  →  commerce revenue")

    o1, o2, o3, o4 = st.columns(4)
    o1.metric("Paid Spend", money(kpis.get("spend"), paid_currency) if kpis else "n/a")
    o2.metric("Paid Impressions", number(kpis.get("impressions")) if kpis else "n/a")
    o3.metric(
        f"Streaming Lift ({impact_window_hours}h)",
        f"{summary.lift:,.0f}" if summary else "n/a",
        f"{summary.lift_percent:,.1f}%" if summary and summary.lift_percent is not None else None,
    )
    o4.metric("Product Revenue", f"${commerce_model.gross_revenue:,.0f}" if commerce_has_data else "n/a")

    if paid_view.empty and summary is None and not commerce_has_data and not demo_mode:
        st.info(
            "Welcome. Nothing is loaded yet. Use the sidebar to upload streaming data, paid media reports and sales, "
            "or switch on Demo mode (Advanced / Demo, at the bottom of the sidebar) to explore with simulated data."
        )

    if market_view is not None and not paid_view.empty:
        if primary_market != "Global" and primary_market not in set(paid_view["market"].astype(str).str.upper()):
            flags.append(
                (
                    "info",
                    f"The sidebar primary market is {primary_market}; paid media markets are "
                    f"{', '.join(sorted(paid_view['market'].astype(str).unique())[:8])}. Check that streaming and paid media cover the same markets.",
                )
            )
    if flags:
        with st.expander(f"Data checks ({len(flags)})", expanded=any(level == "warning" for level, _ in flags)):
            for level, message in flags:
                (st.warning if level == "warning" else st.caption)(message if level == "warning" else f"Note: {message}")

# -----------------------------
# CAMPAIGN RECAP (optional)
# -----------------------------

with box_recap:
    st.markdown("---")
    with st.expander("Campaign recap (optional)", expanded=False):
        if paid_view.empty:
            st.caption("Load paid media data to generate a recap.")
        else:
            streaming_payload = None
            if summary is not None:
                streaming_payload = {
                    "window": f"{impact_window_hours}h",
                    "actual": summary.actual,
                    "expected": summary.expected,
                    "lift_percent": summary.lift_percent,
                }
            recap_table = campaign_market_table(paid_view, as_of, thresholds)
            recap_text = build_recap(
                artist=artist_name,
                release=song_title,
                campaign_id=opus_campaign_id,
                kpis=kpis,
                currency=paid_currency,
                platforms=sorted(paid_view["platform"].unique().tolist()),
                pacing=kpis.get("pacing"),
                market_table=recap_table,
                as_of=as_of,
                best_audience_cost=best.get("audience_cost"),
                best_audience_engaging=best.get("audience_engaging"),
                best_creative_cost=best.get("creative_cost"),
                streaming=streaming_payload,
            )
            st.text_area("Recap (copy or download)", recap_text, height=420)
            st.download_button("Download recap (.txt)", recap_text, file_name="lollie_campaign_recap.txt")
            st.caption("Built only from the numbers loaded above. It does not explain why results happened.")

# -----------------------------
# EXPLANATION
# -----------------------------

with box_help:
    st.markdown(
        """
### How to read this dashboard

**One flow, one page**
Paid advertising and organic social posts feed streaming performance, which sits next to commerce revenue. Sections A to F follow that flow from top to bottom.

**Data Source Mode**
The streaming section reads real data you provide:

* **CSV / Excel upload** reads hourly or daily streaming data and lets you map the timestamp, actual streams, and expected baseline columns.
* **Manual entry** lets you type expected and actual totals for the impact window so the KPIs, lift estimate, and summary chart update.
* **Demo mode** (Advanced / Demo in the sidebar) adds clearly labeled simulated data for training. It is never mixed with real data.

**Expected Baseline Streams**
The estimate of how many streams the track would have received without the selected social, video, or campaign event.

**Actual Streams**
The stream count after the selected social/video event goes live.

**Estimated Social Lift**
The difference between actual streams and expected baseline streams during the selected impact window.

**Formula**
Estimated Social Lift = Actual Streams - Expected Baseline Streams

This is an observational, modeled comparison. It does not prove that a post or an ad campaign caused the change.

**Impact Window**
The selected measurement period after the post or video event. A 24-hour window is useful for fast TikTok/Reels/Shorts spikes. A 72-hour or 168-hour window is better for slower campaign effects, catalog activity, and YouTube content. Daily files are measured in whole days.

**Paid Media Performance**
Spend, impressions, views, engagements, clicks, CPM, CPC and CTR come straight from your platform exports. Results (landing page views, video views, clicks, engagements) are never added together across types. Budget pacing compares spend so far with an even spend across each flight. Forecast attainment projects results to the end of the flight and compares them with the goal.

**Audience & Creative Performance**
Audiences and creatives are compared only on compatible numbers: cost per result within one result type, and engagement rate within one platform.

**Commerce Revenue Attribution**
Product revenue that may be associated with the social and streaming impact window. Product categories include vinyl, CDs, cassettes, deluxe editions, box sets, signed products, apparel, accessories, posters, merch bundles, digital downloads, fan memberships, and ticket or VIP upsells. Commerce can come from an uploaded file, dated sales you type in, or (Demo mode only) an auto estimate.

**Commerce Overlay**
When enabled, the chart can overlay attributed product revenue or units on the streaming trend using a separate right-side axis, because streams and revenue are different measurements.

**Ad Credits & Funding**
A compact summary of partner-funded allocations, billing credits and prepaid funds. Nothing is redeemed or pulled from ad accounts automatically.

**Important note**
Lollie works with the data you give it. Demo mode uses simulated data only. It is designed to show the logic and workflow of a music analytics tool, not to represent real Opus, DSP, advertising platform, D2C, retail, financial, or confidential label data unless connected to approved internal systems.

Conceptualized and designed by Alexander DiFiore, Rhino. Named "lollie" after his two beloved cats, Lily and Ollie.
"""
    )

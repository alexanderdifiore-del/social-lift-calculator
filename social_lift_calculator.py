"""Lollie V2: paid media and streaming intelligence.

Question this prototype answers: when we run paid media campaigns, what happens to the
streaming performance of the music we are promoting?

Everything is observational. Lollie compares streaming during and after a campaign with
a baseline from before it. It does not claim the advertising caused any change.
Real files are processed in this session only; nothing is sent to any outside service.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from lollie.analysis.baseline import AnalysisSettings, aggregate_daily, analyze_campaign_window, baseline_window
from lollie.analysis.campaigns import CampaignDates, campaign_dates, overlap_notes
from lollie.analysis.markets import PAID, market_comparison, market_rank_note
from lollie.analysis.relationships import lag_relationship, spend_series
from lollie.branding import render_lollie_header, render_section_title
from lollie.demo import DEMO_LABEL, load_demo
from lollie.geo import ALL_MARKETS_CODE
from lollie.paid.timeseries import daily_series
from lollie.streams.tracks import (
    daily_scope_totals,
    match_streams,
    tracks_from_stream_frame,
)
from lollie.summary import build_summary
from lollie.ui.campaign_tracks import choose_campaign_scope
from lollie.ui.paid_sections import (
    UPLOAD_TYPES,
    PaidData,
    ingest_uploaded_files,
    pick_currency,
    show_issues,
)
from lollie.ui.sections import (
    render_campaign_comparison,
    render_market_section,
    render_paid_section,
    render_source_streams,
    render_streaming_section,
    render_track_breakdown,
    results_sentences,
)
from lollie.ui.stream_import import StreamData, ingest_stream_files

st.set_page_config(page_title="lollie", page_icon="🍭", layout="wide")

render_lollie_header("paid media • streaming intelligence")

# The Demo switch sits at the bottom of the sidebar but is needed first; Streamlit has
# already stored its value before the script runs.
demo_mode = bool(st.session_state.get("lollie_demo_mode", False))


@st.cache_data(show_spinner=False)
def _demo_data():
    return load_demo()


# -----------------------------
# SIDEBAR
# -----------------------------

st.sidebar.title("Campaign Inputs")

st.sidebar.subheader("1 · Paid media report")
if demo_mode:
    st.sidebar.caption("Demo mode is on: synthetic data is shown and uploaded files are ignored.")
paid_files = st.sidebar.file_uploader(
    "WAVO or other advertising report (CSV or Excel)",
    type=UPLOAD_TYPES,
    accept_multiple_files=True,
    key="paid_upload",
    disabled=demo_mode,
    help="Daily rows with campaign, date, country, platform and spend work best. Column matching is shown after upload.",
)
paid_default_currency = st.sidebar.selectbox(
    "Currency if the file does not say", ["USD", "EUR", "GBP", "CAD", "AUD", "MXN", "BRL"], key="paid_currency"
)

st.sidebar.subheader("2 · Streaming report")
stream_files = st.sidebar.file_uploader(
    "Opus or other approved streaming export (CSV or Excel)",
    type=UPLOAD_TYPES,
    accept_multiple_files=True,
    key="stream_upload",
    disabled=demo_mode,
    help="Daily streams by date, with track, country and service when available.",
)
track_file = st.sidebar.file_uploader(
    "3 · Track list for a playlist (optional)",
    type=UPLOAD_TYPES,
    key="track_upload",
    disabled=demo_mode,
    help="A list of the tracks on the playlist or in the campaign: title, ISRC and optional added / removed dates.",
)

st.sidebar.markdown("---")
st.sidebar.subheader("Analysis windows")
baseline_days = st.sidebar.slider(
    "Baseline length (days before launch)", 7, 56, 28, help="Streams in these days set the expected level."
)
post_days = st.sidebar.slider(
    "After-campaign window (days)", 0, 28, 14, help="Days after the campaign ends that are checked for a lingering change."
)

st.sidebar.markdown("---")
st.sidebar.subheader("Opus / Track Info")
opus_campaign_id = st.sidebar.text_input("Opus Campaign ID (optional)", "", help="Reference only; shown in the summary.")
release_phase = st.sidebar.selectbox(
    "Release Phase (optional)",
    ["Not specified", "Pre-release", "Release week", "Catalog/reactivation", "Tour moment", "Sync/viral moment"],
    help="Context only; it does not change any numbers.",
)

st.sidebar.markdown("---")
st.sidebar.subheader("Social Post Event (optional)")
mark_post = st.sidebar.checkbox("Mark an organic social post on the chart", False)
organic_posts: list[tuple[pd.Timestamp, str]] = []
impact_days = 2
if mark_post:
    post_platform = st.sidebar.selectbox(
        "Platform",
        ["TikTok", "Instagram Reels", "YouTube Shorts", "YouTube Video", "YouTube Visualizer", "YouTube Music Video",
         "YouTube Live Performance", "Snapchat"],
    )
    post_type = st.sidebar.selectbox("Post Type", ["Organic artist post", "Influencer post", "UGC trend"])
    post_date = st.sidebar.date_input("Post Date", datetime.now().date())
    impact_days = st.sidebar.slider(
        "Impact Window Length (days)", 1, 7, 2, help="Days after the post that are shaded on the chart."
    )
    organic_posts.append((pd.Timestamp(post_date), f"{post_platform} · {post_type}"))
with st.sidebar.expander("More organic posts to mark on the chart"):
    extra_posts_text = st.text_area(
        "One per line: date, label",
        value="",
        placeholder="2026-03-10, Instagram Reel",
        help="Adds a dotted marker to the streaming chart. Nothing else is changed.",
        key="extra_posts_text",
    )
for line in extra_posts_text.splitlines():
    if not line.strip():
        continue
    date_text, _, label = line.partition(",")
    parsed = pd.to_datetime(date_text.strip(), errors="coerce")
    if pd.notna(parsed):
        organic_posts.append((parsed.normalize(), label.strip() or "Organic post"))

st.sidebar.markdown("---")
with st.sidebar.expander("Advanced / Demo", expanded=demo_mode):
    st.toggle(
        "Demo mode (synthetic data)",
        key="lollie_demo_mode",
        help="Shows clearly labelled synthetic advertising and streaming data so you can see how the dashboard works. "
        "It is never mixed with real data.",
    )
    st.caption("Demo mode is for practice only. Turn it off to work with your own files.")
    gap_days = st.slider("Leave out days just before launch", 0, 7, 0, help="Skips a ramp-up period before the campaign starts.")
    min_baseline_days = st.slider("Minimum baseline days with data", 3, 21, 7)
    low_paid_pct = st.slider(
        "Count a country as low paid below (% of spend)", 0, 10, 2,
        help="Countries below this share of spend are listed as 'Reference only'.",
    )
    show_trend = st.checkbox("Show 7-day trend line", True)

settings = AnalysisSettings(
    baseline_days=baseline_days, post_days=post_days, gap_days=gap_days, min_baseline_days=min_baseline_days
)

# -----------------------------
# LOAD DATA
# -----------------------------

import_area = st.container()

if demo_mode:
    demo_paid, demo_streams, demo_issues = _demo_data()
    paid = PaidData(frame=demo_paid, issues=[], is_demo=True)
    streams = StreamData(frame=demo_streams, issues=[], is_demo=True)
    paid_issues = stream_issues = []
else:
    paid = ingest_uploaded_files(paid_files, paid_default_currency, import_area) if paid_files else PaidData()
    streams = ingest_stream_files(stream_files, import_area) if stream_files else StreamData()
    paid_issues, stream_issues = paid.issues, streams.issues

if demo_mode:
    st.warning(f"**DEMO MODE.** {DEMO_LABEL} Turn off Demo mode in the sidebar (Advanced / Demo) to use only your own data.")

paid_frame, stream_frame = paid.frame, streams.frame

if paid.is_empty and streams.is_empty:
    render_section_title("Paid Media & Streaming Intelligence")
    st.markdown(
        """
**Welcome.** Lollie answers one question: *when we run paid media campaigns, what happens to the streaming performance
of the music we are promoting?*

Nothing is loaded yet. To get started:

1. In the sidebar, upload a **paid media report** (WAVO or another advertising export, CSV or Excel).
2. Upload a **streaming report** (Opus or another approved export, CSV or Excel).
3. Choose the artist, campaign and song in **Campaign Overview** below. If the report lists a playlist, choose the tracks on it.

Want to look around first? Open **Advanced / Demo** at the bottom of the sidebar and switch on Demo mode. It uses clearly
labelled synthetic data. Practice files you can upload are in the `sample_data` folder.
"""
    )
    st.stop()

# -----------------------------
# A · CAMPAIGN OVERVIEW
# -----------------------------

render_section_title("A · Campaign Overview")

artists = sorted(
    {a for a in paid_frame.get("artist", pd.Series(dtype=object)).dropna().astype(str)}
    | {a for a in stream_frame.get("artist", pd.Series(dtype=object)).dropna().astype(str) if a}
)
filters_top = st.columns(4)
if artists:
    artist_choice = filters_top[0].selectbox("Artist", artists if len(artists) == 1 else ["All artists"] + artists, key="f_artist")
else:
    artist_choice = filters_top[0].text_input("Artist (not in files)", "", key="f_artist_text") or "All artists"
artist_filter = None if artist_choice == "All artists" else artist_choice

paid_a = paid_frame
if not paid_a.empty and artist_filter:
    paid_a = paid_a[(paid_a["artist"] == artist_filter) | paid_a["artist"].isna()]
streams_a = stream_frame
if not streams_a.empty and artist_filter:
    streams_a = streams_a[(streams_a["artist"] == artist_filter) | (streams_a["artist"] == "")]

campaign_choice = None
campaign_rows = paid_a.iloc[0:0]
if not paid_a.empty:
    campaigns = sorted(paid_a["campaign_name"].dropna().unique().tolist())
    campaign_choice = filters_top[1].selectbox("Campaign", campaigns, key="f_campaign")
    campaign_rows = paid_a[paid_a["campaign_name"] == campaign_choice]
else:
    filters_top[1].selectbox("Campaign", ["No paid media report loaded"], disabled=True, key="f_campaign_none")

platforms = sorted(campaign_rows["platform"].dropna().unique().tolist()) if not campaign_rows.empty else []
platform_choice = filters_top[2].multiselect(
    "Advertising platform", platforms, default=platforms, key=f"f_platform_{campaign_choice}", disabled=not platforms
)

paid_market_labels = (
    sorted(campaign_rows["market"].dropna().unique().tolist()) if not campaign_rows.empty else []
)
paid_label_to_code = {}
if not campaign_rows.empty:
    for label, code in campaign_rows[["market", "market_code"]].drop_duplicates().itertuples(index=False):
        paid_label_to_code[label] = code
stream_label_to_code = {}
if not streams_a.empty:
    for label, code in streams_a[["market", "market_code"]].drop_duplicates().itertuples(index=False):
        if code != ALL_MARKETS_CODE:
            stream_label_to_code[label] = code
all_label_to_code = {**stream_label_to_code, **paid_label_to_code}
market_options = sorted(all_label_to_code)
default_markets = [m for m in paid_market_labels if paid_label_to_code.get(m) not in (None, ALL_MARKETS_CODE)]
if not default_markets:
    default_markets = [m for m in market_options]
market_choice = filters_top[3].multiselect(
    "Country / market",
    market_options,
    default=[m for m in default_markets if m in market_options],
    key=f"f_market_{campaign_choice}",
    help="Streaming is totalled for these countries. By default these are the countries the campaign advertised in.",
)

filters_bottom = st.columns([1, 2])
dsps = sorted({d for d in streams_a["dsp"].unique() if d not in ("All DSPs",)}) if not streams_a.empty else []
dsp_choice = filters_bottom[0].selectbox("DSP", ["All DSPs"] + dsps, key="f_dsp", disabled=streams_a.empty)

paid_campaign = campaign_rows
if not paid_campaign.empty:
    if platform_choice:
        paid_campaign = paid_campaign[paid_campaign["platform"].isin(platform_choice)]
    chosen_paid_rows = paid_campaign[
        paid_campaign["market"].isin(market_choice) | (paid_campaign["market_code"] == ALL_MARKETS_CODE)
    ]
    paid_campaign = chosen_paid_rows

if not paid_campaign.empty:
    currency = pick_currency(paid_campaign)
    paid_campaign = paid_campaign[paid_campaign["currency"] == currency].reset_index(drop=True)
else:
    currency = paid_default_currency

dates = campaign_dates(paid_campaign)
manual_dates = False
if not dates.known:
    manual_dates = True
    with filters_bottom[1]:
        st.caption("No campaign dates in the paid media data. Enter them to analyse streaming.")
        date_cols = st.columns(2)
        manual_start = date_cols[0].date_input("Campaign start", value=None, key="manual_start")
        manual_end = date_cols[1].date_input("Campaign end", value=None, key="manual_end")
    if manual_start and manual_end:
        dates = CampaignDates(
            pd.Timestamp(manual_start), pd.Timestamp(manual_end), False, "Campaign dates were entered by hand."
        )

# Promoted song / playlist
scope_box = st.container()
stream_tracks = tracks_from_stream_frame(streams_a)
scope, scope_notes = choose_campaign_scope(
    stream_tracks, campaign_rows, track_file, key=f"scope_{campaign_choice}", container=scope_box
)
matched, coverage = match_streams(streams_a, scope.tracks) if not scope.tracks.empty else (streams_a.iloc[0:0], pd.DataFrame())
analysis_ready = not matched.empty and dates.known
if scope.mode != "single" and not scope.tracks.empty and not coverage.empty:
    with st.expander("Which tracks were found in the streaming data"):
        st.dataframe(coverage, width="stretch", hide_index=True)
        missing = coverage[coverage["Matched by"] == "Not found in streaming data"]
        if not missing.empty:
            st.warning(
                f"{len(missing)} listed track(s) were not found in the streaming data and are not included: "
                + ", ".join(missing["Track"].head(8))
                + "."
            )
        if matched.attrs.get("collapsed_rows"):
            st.warning(
                f"{matched.attrs['collapsed_rows']} streaming row(s) described the same track twice (for example with and "
                "without an ISRC); only the larger was kept so streams are not double counted."
            )

if dates.known:
    tiles = st.columns(5)
    tiles[0].metric("Campaign start", f"{dates.start:%b %d, %Y}")
    tiles[1].metric("Campaign end", f"{dates.end:%b %d, %Y}")
    tiles[2].metric("Length", f"{(dates.end - dates.start).days + 1} days")
    tiles[3].metric("Promoting", scope.label if not scope.tracks.empty else "Not selected")
    tiles[4].metric("Countries", len(market_choice) if market_choice else "All")
    if dates.note:
        st.caption(dates.note)

chosen_codes = sorted({all_label_to_code[m] for m in market_choice if all_label_to_code.get(m) and all_label_to_code[m] != ALL_MARKETS_CODE})
streaming_codes = chosen_codes if chosen_codes else None

daily_all = daily_scope_totals(matched, dsp_choice) if not matched.empty else pd.DataFrame()
no_country_data = not daily_all.empty and set(daily_all["market_code"].unique()) <= {ALL_MARKETS_CODE}
if no_country_data:
    streaming_codes = None

view_range = None
if dates.known:
    base_start, _ = baseline_window(dates.start, settings)
    default_view = (base_start.date(), (dates.end + pd.Timedelta(days=post_days)).date())
    picked = st.date_input(
        "Date range shown",
        value=default_view,
        key=f"f_range_{campaign_choice}_{baseline_days}_{post_days}_{dates.start:%Y%m%d}",
        help="Changes the dates shown in the charts and paid media totals. The analysis windows stay tied to the campaign dates.",
    )
    if isinstance(picked, (tuple, list)) and len(picked) == 2:
        view_range = (pd.Timestamp(picked[0]), pd.Timestamp(picked[1]))

# paid view for section B (date-range filtered)
paid_view = paid_campaign
if view_range and not paid_view.empty:
    in_range = paid_view["date"].isna() | ((paid_view["date"] >= view_range[0]) & (paid_view["date"] <= view_range[1]))
    paid_view = paid_view[in_range]

# -----------------------------
# B · PAID MEDIA PERFORMANCE
# -----------------------------

render_section_title("B · Paid Media Performance")
if paid.is_empty:
    st.info("No paid media report loaded. Upload a WAVO or advertising report in the sidebar.")
    kpis, results_table = {}, pd.DataFrame()
else:
    kpis, results_table = render_paid_section(paid_view, currency)

# -----------------------------
# C · STREAMING INTELLIGENCE
# -----------------------------

render_section_title("C · Streaming Intelligence")
analysis = None
relationship = None
agg_notes: list[str] = []
spend_daily = pd.DataFrame()
if streams.is_empty:
    st.info("No streaming report loaded. Upload a streaming export in the sidebar to see streams around the campaign.")
elif scope.tracks.empty:
    st.info("Choose the promoted song or playlist in Campaign Overview above.")
elif matched.empty:
    st.warning("None of the selected tracks were found in the streaming data, so there is nothing to analyse.")
elif not dates.known:
    st.info("Enter campaign start and end dates in Campaign Overview to compare streaming before, during and after.")
else:
    series, agg_notes = aggregate_daily(daily_all, streaming_codes)
    if no_country_data:
        agg_notes = ["The streaming file has no country column, so streams for all countries are used and country filters do not apply."] + agg_notes
    if series.empty:
        st.warning("There is no streaming data for the selected countries and DSP.")
    else:
        analysis = analyze_campaign_window(series, dates.start, dates.end, settings)
        if not paid_campaign.empty:
            spend_daily = daily_series(paid_campaign)[["date", "spend"]]
            frame_series = analysis.series.set_index("date")
            relationship = lag_relationship(
                spend_series(paid_campaign, dates.start, dates.end), frame_series["actual"], frame_series["expected"]
            )
        market_text = ", ".join(market_choice[:4]) + ("…" if len(market_choice) > 4 else "") if market_choice else "all countries"
        render_streaming_section(
            analysis,
            title=f"{scope.label}: actual vs expected streams ({market_text}, {dsp_choice})",
            spend_daily=spend_daily,
            currency=currency,
            organic_posts=organic_posts,
            impact_days=impact_days,
            show_trend=show_trend,
            view_range=view_range,
            notes=agg_notes,
            relationship=relationship,
        )
        if scope.track_count > 1:
            render_track_breakdown(matched, scope.tracks, dsp_choice, streaming_codes, dates.start, dates.end, settings)
        render_source_streams(matched)

source_present = bool(not matched.empty and (matched["scope"] != "total").any())

# -----------------------------
# D · MARKET COMPARISON
# -----------------------------

render_section_title("D · Market Comparison")
market_table = pd.DataFrame()
rank_note = None
if paid.is_empty or streams.is_empty or not analysis_ready:
    st.info("Country comparison needs a paid media report, a streaming report, a selected song or playlist and campaign dates.")
else:
    paid_all_markets = campaign_rows
    if platform_choice:
        paid_all_markets = paid_all_markets[paid_all_markets["platform"].isin(platform_choice)]
    paid_all_markets = paid_all_markets[paid_all_markets["currency"] == currency]
    market_table, market_analyses, market_relations = market_comparison(
        paid_all_markets, daily_all, dates.start, dates.end, settings, low_paid_share=low_paid_pct / 100
    )
    hidden = 0
    if not market_table.empty:
        streaming_only = market_table[market_table["Paid activity"] != PAID]
        keep_low = streaming_only.sort_values("Avg daily streams before", ascending=False).head(8).index
        drop = streaming_only.index.difference(keep_low)
        hidden = len(drop)
        market_table = market_table.drop(index=drop).reset_index(drop=True)
    rank_note = market_rank_note(market_table)
    render_market_section(market_table, rank_note, hidden)

# -----------------------------
# E · CAMPAIGN SUMMARY
# -----------------------------

render_section_title("E · Campaign Summary")
if paid.is_empty and streams.is_empty:
    st.info("The summary appears once data is loaded.")
else:
    other_paid = paid_a[paid_a["currency"] == currency] if not paid_a.empty else paid_a
    overlaps = (
        overlap_notes(other_paid, campaign_choice, dates.start, dates.end, settings, chosen_codes or None)
        if (campaign_choice and dates.known and not other_paid.empty)
        else []
    )
    data_notes = [i.message for i in paid_issues + stream_issues + scope_notes if i.level in ("warning", "error")]
    data_notes += agg_notes
    if not paid.is_empty and not paid_campaign.empty and paid_campaign["market_code"].isna().any():
        data_notes.append("Some paid media rows have countries Lollie could not match, so they are left out of country comparisons.")
    results_lines = results_sentences(results_table, currency) if not results_table.empty else []
    summary = build_summary(
        campaign=campaign_choice or "(no paid campaign)",
        scope_label=scope.label if not scope.tracks.empty else "the selected music",
        currency=currency,
        kpis=kpis or {},
        results_text=results_lines,
        analysis=analysis,
        market_table=market_table,
        rank_note=rank_note,
        relationship=relationship,
        overlap_notes=overlaps,
        data_notes=data_notes,
        dates_note=dates.note if dates.known else "",
        source_attributed_present=source_present,
        membership_verified=scope.membership_verified,
        multi_track=scope.mode != "single",
    )
    if not kpis and analysis is None:
        st.info("Load a paid media report and a streaming report, then choose a campaign and song, to see the summary.")
    else:
        header_bits = [bit for bit in (
            f"Opus campaign {opus_campaign_id}" if opus_campaign_id.strip() else "",
            f"Release phase: {release_phase}" if release_phase != "Not specified" else "",
            f"Playlist reference: {scope.playlist_url}" if scope.playlist_url else "",
        ) if bit]
        if header_bits:
            st.caption(" · ".join(header_bits))
        markdown = summary.to_markdown(f"{campaign_choice or 'Campaign'} summary")
        st.markdown(markdown.replace("$", "\\$"))
        st.download_button("Download summary (text)", markdown, file_name="lollie_campaign_summary.md", key="dl_summary")
    if not other_paid.empty and other_paid["campaign_name"].nunique() > 1 and not daily_scope_totals(matched).empty:
        with st.expander("Compare with other campaigns"):
            render_campaign_comparison(other_paid, daily_scope_totals(matched, dsp_choice), settings, currency)
    if demo_mode:
        st.caption(DEMO_LABEL)

with st.expander("Import notes"):
    notes_shown = False
    for issues in (paid_issues, stream_issues):
        if issues:
            show_issues(issues)
            notes_shown = True
    if not notes_shown:
        st.caption("No import notes.")

with st.expander("How to read this dashboard"):
    st.markdown(
        """
* **Expected** streams come from the days before the campaign (see *How the expected baseline is calculated* under the chart).
* **Observed streaming change** and **Change versus baseline** compare actual streams with that expected level. They describe what
  happened; they do not prove the advertising caused it.
* A **Potential positive relationship** means ad spend and streaming change moved up and down together on the same or following days.
  It is a pattern to investigate, not a result.
* Streams credited to a playlist or source are kept separate from total track streams and never added to them.
* Countries with little or no paid activity are shown for reference only. They are not a validated comparison group.
* **Demo mode** uses synthetic data only. It is never mixed with real data.
"""
    )

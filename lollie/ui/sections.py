"""Dashboard sections B to E (section A is built in the main script because it owns the filters)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from lollie.analysis.baseline import AnalysisSettings, WindowAnalysis, label_change
from lollie.analysis.campaigns import campaign_comparison, repeated_pattern_note
from lollie.analysis.relationships import Relationship
from lollie.streams.tracks import (
    daily_scope_totals,
    source_attributed_totals,
)
from lollie.analysis.baseline import aggregate_daily, analyze_campaign_window
from lollie.ui.charts import market_chart, streaming_intelligence_chart
from lollie.ui.paid_sections import by_country_table, money, number, render_kpis, render_results, show_table

BASELINE_EXPLAINER = """
**How the expected baseline is worked out**

1. Lollie looks at the days just before the campaign started (the *baseline window*, set in the sidebar).
2. It uses only days that have streaming data. Missing days are never filled in or counted as zero.
3. If every weekday has at least 3 baseline days, the expected streams for a day are the **median of the same weekday**
   in the baseline window (so a Friday is compared with baseline Fridays). Otherwise it is the **median of all baseline days**.
4. That expected level is carried forward across the campaign and the after-campaign period.
5. **Observed change** is actual streams minus expected streams, adding up only days that have streaming data.
   **Change versus baseline** is that difference as a percentage of expected streams.

The baseline does not adjust for a rising or falling trend, new releases, playlist adds, social posts or anything else
that changed at the same time. It shows what happened compared with a quiet period, not what the advertising caused.
"""


def pct_text(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:+.1%}"


def render_paid_section(paid_view: pd.DataFrame, currency: str) -> tuple[dict, pd.DataFrame]:
    """Section B: compact paid media performance."""
    if paid_view.empty:
        st.info("No paid media rows for this selection. Upload a WAVO / advertising report in the sidebar.")
        return {}, pd.DataFrame()
    kpis = render_kpis(paid_view, currency)
    results = render_results(paid_view, currency)
    countries = by_country_table(paid_view)
    if len(countries) > 1 or (len(countries) == 1 and countries.iloc[0]["Country"] != "All markets"):
        st.markdown("**By country**")
        show_table(
            countries,
            {
                "Spend": "{:,.0f}", "Impressions": "{:,.0f}", "Clicks": "{:,.0f}", "Landing page views": "{:,.0f}",
                "CPM": "{:,.2f}", "CPC": "{:,.2f}",
            },
        )
    return kpis, results


def results_sentences(results: pd.DataFrame, currency: str) -> list[str]:
    sentences = []
    for _, row in results.iterrows():
        text = f"{row['Result type']}: {number(row['Results'])} results"
        if row.get("Cost per result") is not None and pd.notna(row.get("Cost per result")):
            text += f" at {money(row['Cost per result'], currency, 3)} per result"
        if row.get("Goal") and pd.notna(row.get("Goal")) and row["Goal"] > 0:
            text += f", {row['Results'] / row['Goal']:.0%} of the {number(row['Goal'])} goal"
        sentences.append(text + ".")
    if len(sentences) > 1:
        sentences.append("Different result types are reported separately and are not combined.")
    return sentences


def render_streaming_tiles(analysis: WindowAnalysis) -> None:
    columns = st.columns(5)
    columns[0].metric("Before campaign", number(analysis.baseline.average), help="Average daily streams in the baseline window.")
    columns[1].metric("During campaign", number(analysis.during.average), help="Average daily streams while the campaign ran.")
    columns[2].metric(
        "After campaign",
        number(analysis.post.average),
        help="Average daily streams in the days after the campaign ended.",
    )
    columns[3].metric(
        "Observed streaming change",
        "n/a" if analysis.observed_change is None else f"{analysis.observed_change:+,.0f}",
        help="Actual streams minus expected streams, over campaign days that have data.",
    )
    columns[4].metric(
        "Change versus baseline",
        pct_text(analysis.pct_change),
        delta=label_change(analysis.pct_change) if analysis.pct_change is not None else None,
        delta_color="off",
    )
    coverage = analysis.during.coverage
    st.caption(
        f"Baseline: {analysis.method.lower()} from {analysis.baseline.start:%b %d} to {analysis.baseline.end:%b %d} "
        f"({analysis.baseline.days_with_data} of {analysis.baseline.days_in_window} days with data). "
        + (f"Streaming data covers {analysis.during.days_with_data} of {analysis.during.days_in_window} campaign days." if coverage is not None else "")
    )


def render_streaming_section(
    analysis: WindowAnalysis | None,
    *,
    title: str,
    spend_daily: pd.DataFrame,
    currency: str,
    organic_posts: list,
    impact_days: int,
    show_trend: bool,
    view_range: tuple[pd.Timestamp, pd.Timestamp] | None,
    notes: list[str],
    relationship: Relationship | None,
) -> None:
    if analysis is None:
        st.info("Streaming comparison appears here once a streaming report and campaign dates are available.")
        return
    render_streaming_tiles(analysis)
    for note in analysis.flags + notes:
        st.warning(note)
    if not analysis.usable:
        st.info("A before / during comparison needs streaming data in both the baseline window and the campaign.")
    st.plotly_chart(
        streaming_intelligence_chart(
            analysis,
            title=title,
            spend_daily=spend_daily,
            currency=currency,
            organic_posts=organic_posts,
            impact_days=impact_days,
            show_trend=show_trend,
            view_range=view_range,
        ),
        width="stretch",
    )
    if analysis.method_text and analysis.usable:
        st.caption(f"Expected baseline: {analysis.method_text}")
    if relationship is not None and relationship.by_lag:
        lag_table = pd.DataFrame(
            {"Days after spend": list(relationship.by_lag), "Correlation": list(relationship.by_lag.values())}
        )
        st.markdown(
            f"**Spend and streaming timing:** {relationship.label} "
            + (f"(best match {relationship.best_lag} day(s) after spend, correlation {relationship.correlation:+.2f}, {relationship.paired_days} days). " if relationship.correlation is not None else "")
            + relationship.note
        )
        with st.expander("Timing detail: spend today versus streaming change 0 to 7 days later"):
            show_table(lag_table, {"Correlation": "{:+.2f}"})
            st.caption(
                "Each row compares daily ad spend with the change in streams (actual minus expected) a set number of days later. "
                "Seven delays were tried, so a moderate match can appear by chance. It shows that two lines moved together, "
                "not that one caused the other."
            )
    elif relationship is not None and relationship.note:
        st.caption(f"Spend and streaming timing: {relationship.note}")
    with st.expander("How the expected baseline is calculated"):
        st.markdown(BASELINE_EXPLAINER)


def render_track_breakdown(
    matched: pd.DataFrame,
    scope_tracks: pd.DataFrame,
    dsp: str,
    market_codes: list[str] | None,
    start: pd.Timestamp,
    end: pd.Timestamp,
    settings: AnalysisSettings,
) -> pd.DataFrame:
    """Song-level view so one track is not hidden inside a playlist total."""
    rows = []
    for track in scope_tracks.itertuples():
        mine = matched[matched["track_key"] == track.track_key]
        daily = daily_scope_totals(mine, dsp)
        series, _ = aggregate_daily(daily, market_codes)
        if series.empty:
            rows.append({"Track": track.title, "Before": None, "During": None, "After": None, "Change vs baseline": None})
            continue
        analysis = analyze_campaign_window(series, start, end, settings)
        rows.append(
            {
                "Track": track.title,
                "Before": analysis.baseline.average,
                "During": analysis.during.average,
                "After": analysis.post.average,
                "Change vs baseline": analysis.pct_change,
            }
        )
    table = pd.DataFrame(rows)
    st.markdown("**Song by song** (average daily streams)")
    show_table(table, {"Before": "{:,.0f}", "During": "{:,.0f}", "After": "{:,.0f}", "Change vs baseline": "{:+.1%}"})
    return table


def render_source_streams(matched: pd.DataFrame) -> bool:
    table = source_attributed_totals(matched)
    if table.empty:
        return False
    with st.expander("Playlist / source-attributed streams (shown separately)"):
        st.caption(
            "These streams were credited to a specific playlist or source. They are a slice of the track's total streams, "
            "so they are not added to the totals above and do not show that the playlist generated the track's streams."
        )
        show_table(table, {"Streams": "{:,.0f}"})
    return True


def render_market_section(table: pd.DataFrame, rank_note: str | None, hidden_rows: int) -> None:
    if table.empty:
        st.info("Country comparison appears here once paid media and streaming data are loaded.")
        return
    st.plotly_chart(market_chart(table), width="stretch")
    shown = table[
        [
            "Market", "Paid activity", "Ad spend", "Landing page views", "Avg daily streams before",
            "Avg daily streams during", "Avg daily streams after", "Observed change (streams)", "Change vs baseline",
            "Reading", "Spend and streaming pattern",
        ]
    ]
    show_table(
        shown,
        {
            "Ad spend": "{:,.0f}", "Landing page views": "{:,.0f}", "Avg daily streams before": "{:,.0f}",
            "Avg daily streams during": "{:,.0f}", "Avg daily streams after": "{:,.0f}",
            "Observed change (streams)": "{:+,.0f}", "Change vs baseline": "{:+.1%}",
        },
    )
    if rank_note:
        st.markdown(rank_note)
    if hidden_rows:
        st.caption(f"{hidden_rows} more streaming-only countries are not listed.")
    st.caption(
        "Countries marked 'Reference only' (little or no paid activity) are shown for context. They are not a control group: they can differ "
        "from paid countries in size, release timing, playlisting and more, so a difference between them and paid countries "
        "does not show what advertising did."
    )
    with st.expander("Country notes and data coverage"):
        detail = table[["Market", "Streaming data coverage", "Notes"]]
        show_table(detail, {"Streaming data coverage": "{:.0%}"})


def render_campaign_comparison(paid: pd.DataFrame, daily: pd.DataFrame, settings: AnalysisSettings, currency: str) -> pd.DataFrame:
    table, _ = campaign_comparison(paid, daily, settings)
    if len(table) < 2:
        return table
    st.markdown("**This campaign compared with other campaigns**")
    show_table(
        table,
        {
            "Ad spend": "{:,.0f}", "Landing page views": "{:,.0f}", "Avg daily streams before": "{:,.0f}",
            "Avg daily streams during": "{:,.0f}", "Avg daily streams after": "{:,.0f}", "Change vs baseline": "{:+.1%}",
            "Observed change (streams)": "{:+,.0f}", "Streaming data coverage": "{:.0%}",
            "Start": "{:%Y-%m-%d}", "End": "{:%Y-%m-%d}",
        },
    )
    note = repeated_pattern_note(table)
    if note:
        st.markdown(note)
    st.caption(f"Ad spend is shown in {currency}. Campaigns are each compared with their own baseline, in the countries where they advertised.")
    return table

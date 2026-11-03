"""Dashboard sections B to E (section A is built in the main script because it owns the filters)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from lollie.analysis.baseline import AnalysisSettings, WindowAnalysis
from lollie.analysis.streaming import ScopeAnalysis
from lollie.summary import describe_change
from lollie.valuation import LABEL as VALUE_LABEL, TOOLTIP as VALUE_TOOLTIP, StreamingValue
from lollie.analysis.campaigns import campaign_comparison, repeated_pattern_note
from lollie.analysis.relationships import Relationship
from lollie.streams.tracks import source_attributed_totals
from lollie.ui.charts import market_chart, streaming_intelligence_chart
from lollie.ui.paid_sections import by_country_table, money, number, render_kpis, render_results, show_table

BASELINE_EXPLAINER = """
**How the Global Catalog baseline is worked out**

Established catalog recordings are not flat, so Lollie does not assume a fixed line. It asks what *normal* looks like for
each recording, using only the recording's own history from before the campaign:

1. **History window.** The 14, 28, 56 (preferred) or 90 days before launch, chosen in the sidebar. Days without streaming
   data are never filled in or counted as zero, and nothing from the campaign or after it is used.
2. **Normal level.** The median daily streams in that window, so a few big days cannot pull it up.
3. **Weekly pattern.** If the window has enough days, each weekday is compared with its own usual level
   (a Friday with Fridays).
4. **Gradual growth or decline.** If the history shows a steady rise or fall, the baseline follows it (and fades it out
   rather than assuming it continues forever). Short histories are not given a trend.
5. **Spikes.** Days far outside the recording's usual pattern, such as a viral day or a reporting error, are set aside
   when the baseline is built. They still show in the actual line.
6. **Normal variability.** Lollie measures how far this recording's days and multi-day stretches normally land from the
   baseline (and how far the same method missed in earlier periods). A change is only called *outside normal variation*
   when it is clearly bigger than that. The same 6% can be large for a very steady song and ordinary for a volatile one.

**Observed streaming change** is actual minus expected streams, adding up only days that have data.
**Percentage change vs. baseline** is that difference as a percentage of expected streams.

The baseline does not know about releases, playlist adds, social posts, press, tours or anything else that changed at the
same time. It shows how streaming compared with the recording's history, not what the advertising caused.
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


def render_streaming_tiles(analysis: WindowAnalysis, value: StreamingValue | None = None) -> None:
    show_value = value is not None and value.enabled
    columns = st.columns(5 if show_value else 4)
    columns[0].metric(
        "Expected Streams",
        number(analysis.during_expected),
        help="Streams the Global Catalog baseline expects over the campaign days that have data. Built only from history before the campaign.",
    )
    columns[1].metric("Actual Streams", number(analysis.during_actual), help="Streams actually reported on those same campaign days.")
    columns[2].metric(
        "Observed Streaming Change",
        "n/a" if analysis.observed_change is None else f"{analysis.observed_change:+,.0f}",
        help="Actual streams minus expected streams. It describes what happened; it does not show what caused it.",
    )
    columns[3].metric(
        "Percentage Change vs. Baseline",
        pct_text(analysis.pct_change),
        delta=analysis.reading if analysis.pct_change is not None else None,
        delta_color="off",
        help="Observed change as a percentage of expected streams, with a reading of whether it is bigger than this recording's normal variation.",
    )
    if show_value:
        columns[4].metric(VALUE_LABEL, value.display, help=VALUE_TOOLTIP)
    coverage = analysis.during.coverage
    st.caption(
        f"Average daily streams: before {number(analysis.baseline.average)}, during {number(analysis.during.average)}, "
        f"after {number(analysis.post.average)}. "
        + (f"Streaming data covers {analysis.during.days_with_data} of {analysis.during.days_in_window} campaign days. " if coverage is not None else "")
        + f"History window: {analysis.baseline.start:%b %d} to {analysis.baseline.end:%b %d} "
        f"({analysis.baseline.days_with_data} of {analysis.baseline.days_in_window} days with data)."
    )
    if show_value:
        if value.calculated:
            st.caption(
                f"{VALUE_LABEL}: {value.streams_change:+,.0f} Spotify streams x \\${value.rate:g} assumed per stream. "
                "A planning estimate only, not revenue, royalties or ad ROI."
            )
        elif value.reason:
            st.caption(f"{VALUE_LABEL}: not calculated. {value.reason}")


def render_baseline_check(analysis: WindowAnalysis) -> None:
    """How well the same baseline method predicted earlier stretches of this recording's own history."""
    check = analysis.backtest
    if check is None:
        return
    with st.expander("Check the baseline against this recording's history"):
        if not check.usable:
            st.caption(f"Not enough earlier history to check the baseline. {check.note}")
            return
        st.markdown(
            f"Lollie pretended the campaign had started on {check.n_origins} earlier dates, built the baseline from only the days "
            f"before each one, and compared its expected streams with what really happened over {check.horizon_days} days.  \n"
            f"- Typical miss (median): **{check.median_abs_error:.1%}** with this baseline, versus {check.naive_median_abs_error:.1%} "
            "with a simple flat baseline.  \n"
            f"- Average direction of the miss: {check.bias:+.1%} (close to zero means no consistent over- or under-shooting).  \n"
            f"- The typical range band contained **{check.band_coverage:.0%}** of days (about 95% is the aim).  \n"
            f"- Misses of this size are what Lollie treats as normal variation for a {check.horizon_days}-day period."
        )
        table = check.table.assign(
            **{"Start": check.table["origin"].dt.strftime("%Y-%m-%d")}
        )[["Start", "expected", "actual", "error"]].rename(
            columns={"expected": "Expected streams", "actual": "Actual streams", "error": "Miss"}
        )
        show_table(table, {"Expected streams": "{:,.0f}", "Actual streams": "{:,.0f}", "Miss": "{:+.1%}"})
        st.caption("Only days before the campaign's history window ends are used. These are practice runs on past data, not campaign results.")


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
    value: StreamingValue | None = None,
    show_band: bool = True,
) -> None:
    if analysis is None:
        st.info("Streaming comparison appears here once a streaming report and campaign dates are available.")
        return
    render_streaming_tiles(analysis, value)
    sentence = describe_change(analysis)
    if sentence:
        st.markdown(sentence.replace("$", "\\$"))
    for note in analysis.flags + notes:
        st.warning(note)
    if not analysis.usable:
        st.info("A before / during comparison needs streaming data in both the history window and the campaign.")
    for note in analysis.context:
        st.caption(note)
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
            show_band=show_band,
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
    if analysis.usable:
        render_baseline_check(analysis)
    with st.expander("How the expected baseline is calculated"):
        st.markdown(BASELINE_EXPLAINER)


def render_track_breakdown(scope: ScopeAnalysis) -> pd.DataFrame:
    """Song-level view so one track is not hidden inside a playlist total."""
    table = scope.track_table()
    st.markdown("**Song by song** (each track has its own baseline; the totals above add them up, counting each track once)")
    show_table(
        table,
        {
            "Expected streams": "{:,.0f}", "Actual streams": "{:,.0f}", "Observed change": "{:+,.0f}", "Change vs baseline": "{:+.1%}",
        },
    )
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
            "Avg daily streams during", "Observed change (streams)", "Change vs baseline", "Reading",
            "Spend and streaming pattern",
        ]
    ].rename(columns={"Avg daily streams before": "Streams/day before", "Avg daily streams during": "Streams/day during",
                      "Observed change (streams)": "Observed change"})
    show_table(
        shown,
        {
            "Ad spend": "{:,.0f}", "Landing page views": "{:,.0f}", "Streams/day before": "{:,.0f}",
            "Streams/day during": "{:,.0f}", "Observed change": "{:+,.0f}", "Change vs baseline": "{:+.1%}",
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
        detail = table[["Market", "Avg daily streams after", "Streaming data coverage", "Notes"]]
        show_table(detail, {"Avg daily streams after": "{:,.0f}", "Streaming data coverage": "{:.0%}"})


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

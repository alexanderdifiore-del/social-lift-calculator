"""Streamlit fragments for the paid-media sections of the unified dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from lollie.imports.file_loader import load_tabular_upload, read_raw_bytes
from lollie.paid.ingest import (
    IngestResult,
    Issue,
    combine_paid_frames,
    detect_platform,
    file_fingerprint,
    normalize_paid_frame,
    suggest_mapping,
)
from lollie.paid.metrics import (
    STATUS_AHEAD,
    STATUS_AT_RISK,
    STATUS_ON_TRACK,
    STATUS_UNAVAILABLE,
    Thresholds,
    aggregate_kpis,
    campaign_market_table,
    overall_pacing,
    pacing_label,
    rate_pct,
    results_by_type,
    status_counts,
)
from lollie.paid.performance import (
    best_cost_effective,
    best_engaging,
    comparable_result_families,
    rank_dimension,
)
from lollie.paid.schema import (
    CANONICAL_FIELDS,
    FIELD_LABELS,
    PLATFORM_OPTIONS,
    RESULT_FAMILIES,
)

PAID_HEADER_HINTS = ("campaign", "spend", "cost", "amount_spent", "impressions", "date", "day")
UPLOAD_TYPES = ["csv", "xlsx", "xls"]

STATUS_STYLE = {
    STATUS_AHEAD: "background-color: #d9f2e4; color: #14532d",
    STATUS_ON_TRACK: "background-color: #e0f4f7; color: #0b5560",
    STATUS_AT_RISK: "background-color: #fde2e2; color: #7f1d1d",
    STATUS_UNAVAILABLE: "background-color: #eeeeee; color: #555555",
}


@dataclass
class PaidData:
    frame: pd.DataFrame = field(default_factory=pd.DataFrame)
    issues: list[Issue] = field(default_factory=list)
    results: list[IngestResult] = field(default_factory=list)
    is_demo: bool = False

    @property
    def is_empty(self) -> bool:
        return self.frame.empty


def money(value: float | None, currency: str = "USD", digits: int = 0) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(currency)
    text = f"{value:,.{digits}f}"
    return f"{symbol}{text}" if symbol else f"{text} {currency}"


def number(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:,.0f}"


def show_issues(issues: list[Issue], *, title: str = "Import checks") -> None:
    if not issues:
        return
    order = {"error": 0, "warning": 1, "info": 2}
    for issue in sorted(issues, key=lambda item: order.get(item.level, 3)):
        if issue.level == "error":
            st.error(issue.message)
        elif issue.level == "warning":
            st.warning(issue.message)
        else:
            st.caption(f"Note: {issue.message}")


def ingest_uploaded_files(files: list, default_currency: str, container) -> PaidData:
    """Read, map and validate uploaded paid-media exports (CSV or Excel)."""
    results: list[IngestResult] = []
    with container:
        for index, uploaded in enumerate(files):
            raw_bytes = read_raw_bytes(uploaded)
            digest = file_fingerprint(raw_bytes)
            key = f"paid_{digest[:10]}_{index}"
            with st.expander(f"Import settings: {uploaded.name}", expanded=False):
                try:
                    raw = load_tabular_upload(uploaded, header_hints=PAID_HEADER_HINTS)
                except Exception as error:  # noqa: BLE001 - shown to the user
                    st.error(f"'{uploaded.name}' could not be read: {error}")
                    continue
                if raw.empty:
                    st.error(f"'{uploaded.name}' has no rows.")
                    continue

                columns = list(raw.columns)
                detected = detect_platform(columns, uploaded.name)
                platform = st.selectbox(
                    "Report source",
                    PLATFORM_OPTIONS,
                    index=PLATFORM_OPTIONS.index(detected),
                    key=f"{key}_platform",
                    help="Detected from the file name and column headings. Change it if it is wrong.",
                )
                suggested = suggest_mapping(columns)
                st.caption("Match each Lollie field to a column in your file. Leave a field blank when the file does not have it.")
                mapping: dict[str, str | None] = {}
                options = ["(not in file)"] + columns
                grid = st.columns(3)
                for position, name in enumerate(CANONICAL_FIELDS):
                    default = suggested.get(name)
                    choice = grid[position % 3].selectbox(
                        FIELD_LABELS.get(name, name),
                        options,
                        index=options.index(default) if default in options else 0,
                        key=f"{key}_{name}",
                    )
                    mapping[name] = None if choice == "(not in file)" else choice
                st.dataframe(raw.head(8), width="stretch")

            result = normalize_paid_frame(
                raw,
                mapping,
                platform,
                default_currency=default_currency,
                source_label=uploaded.name,
            )
            result.file_hash = digest
            results.append(result)
            for issue in result.issues:
                if issue.level in ("error", "warning"):
                    st.warning(f"{uploaded.name}: {issue.message}") if issue.level == "warning" else st.error(
                        f"{uploaded.name}: {issue.message}"
                    )
    frame, combine_issues = combine_paid_frames(results)
    issues = [issue for result in results for issue in result.issues if issue.level == "info"] + combine_issues
    return PaidData(frame=frame, issues=issues, results=results)



def show_table(frame: pd.DataFrame, formats: dict[str, str], status_column: str | None = None) -> None:
    """Show a formatted table; colors statuses when pandas Styler is available."""
    formats = {key: value for key, value in formats.items() if key in frame.columns}
    try:
        styler = frame.style.format(formats, na_rep="n/a")
        if status_column and status_column in frame.columns:
            styler = styler.map(lambda value: STATUS_STYLE.get(value, ""), subset=[status_column])
        st.dataframe(styler, width="stretch", hide_index=True)
    except (AttributeError, ImportError):
        plain = frame.copy()
        for column, pattern in formats.items():
            plain[column] = [("n/a" if pd.isna(value) else pattern.format(value)) for value in plain[column]]
        st.dataframe(plain, width="stretch", hide_index=True)


def pick_currency(frame: pd.DataFrame) -> str:
    """One currency at a time: amounts in different currencies are never added together."""
    currencies = sorted(frame["currency"].dropna().unique().tolist())
    if len(currencies) <= 1:
        return currencies[0] if currencies else "USD"
    spend_by = frame.groupby("currency")["spend"].sum().sort_values(ascending=False)
    ordered = spend_by.index.tolist()
    return st.selectbox(
        "Currency to display",
        ordered,
        help="Your files include more than one currency. Totals are shown for one currency at a time and are never combined.",
    )


def link_campaigns(frame: pd.DataFrame, artist: str, container) -> pd.DataFrame:
    """Manual link between loaded paid campaigns and this artist / release."""
    campaigns = sorted(frame["campaign_name"].dropna().unique().tolist())
    if not campaigns:
        return frame
    default = campaigns
    note = ""
    if frame["artist"].notna().any() and artist.strip():
        needle = artist.strip().lower()
        matches = sorted(
            frame.loc[frame["artist"].fillna("").str.lower() == needle, "campaign_name"].unique().tolist()
        )
        if matches:
            default = matches
            if len(matches) < len(campaigns):
                note = f"{len(campaigns) - len(matches)} campaign(s) list a different artist and are not linked by default."
    signature = abs(hash(tuple(campaigns))) % 10_000_000
    with container:
        chosen = st.multiselect(
            "Paid campaigns linked to this release",
            campaigns,
            default=default,
            key=f"linked_campaigns_{signature}",
            help="Only linked campaigns appear in the paid media sections, the chart overlay and the recap.",
        )
        if note:
            st.caption(note)
    return frame[frame["campaign_name"].isin(chosen)].reset_index(drop=True)


def render_kpis(frame: pd.DataFrame, currency: str, as_of: pd.Timestamp) -> dict:
    kpis = aggregate_kpis(frame)
    row1 = st.columns(5)
    row1[0].metric("Impressions", number(kpis["impressions"]))
    row1[1].metric("Views", number(kpis["views"]))
    row1[2].metric("Engagements", number(kpis["engagements"]))
    row1[3].metric("Clicks", number(kpis["clicks"]))
    row1[4].metric("Spend", money(kpis["spend"], currency))

    pacing = overall_pacing(frame, as_of)
    row2 = st.columns(5)
    row2[0].metric("Total Budget", money(kpis["budget"], currency))
    row2[1].metric(
        "Budget Pacing",
        "n/a" if pacing is None else f"{pacing * 100:,.0f}%",
        help="Spend so far compared with an even spend across each flight. 100% is exactly on pace.",
    )
    if pacing is not None:
        row2[1].caption(pacing_label(pacing))
    row2[2].metric("CPM", money(kpis["cpm"], currency, 2))
    row2[3].metric("CPC", money(kpis["cpc"], currency, 2))
    row2[4].metric("CTR", rate_pct(kpis["ctr"]))
    kpis["pacing"] = pacing
    return kpis


def render_results(frame: pd.DataFrame, currency: str) -> pd.DataFrame:
    """Results are never added across different result types."""
    table = results_by_type(frame)
    if table.empty:
        st.caption("No campaign results were reported in the loaded files, so cost per result is not available.")
        return table
    if len(table) == 1:
        row = table.iloc[0]
        cols = st.columns(4)
        cols[0].metric(f"Results ({row['Result type']})", number(row["Results"]))
        cols[1].metric("Goal", number(row["Goal"]))
        cols[2].metric("Cost per Result", money(row["Cost per result"], currency, 3))
        cols[3].metric("Result Rate", rate_pct(row["Result rate"]))
    else:
        st.caption(
            "Results are reported separately for each result type because different results (for example video views "
            "and landing page views) cannot be added together."
        )
        shown = table.drop(columns=["family"]).copy()
        show_table(
            shown,
            {
                "Results": "{:,.0f}",
                "Goal": "{:,.0f}",
                "Spend": "{:,.2f}",
                "Cost per result": "{:,.3f}",
                "Result rate": "{:.2%}",
            },
        )
    return table


MARKET_FORMATS = {
    "Budget": "{:,.0f}",
    "Spend": "{:,.0f}",
    "Results": "{:,.0f}",
    "Results goal": "{:,.0f}",
    "Forecast attainment": "{:.0%}",
    "CPM": "{:,.2f}",
    "Cost per result": "{:,.3f}",
    "Result rate": "{:.2%}",
    "Pacing": "{:.0%}",
    "Impressions": "{:,.0f}",
    "Clicks": "{:,.0f}",
    "Days remaining": "{:,.0f}",
}


def render_market_table(frame: pd.DataFrame, as_of: pd.Timestamp, thresholds: Thresholds) -> pd.DataFrame:
    table = campaign_market_table(frame, as_of, thresholds)
    if table.empty:
        st.info("No campaign rows to show yet.")
        return table

    counts = status_counts(table)
    chips = st.columns(4)
    for chip, status in zip(chips, [STATUS_AHEAD, STATUS_ON_TRACK, STATUS_AT_RISK, STATUS_UNAVAILABLE]):
        chip.metric(status, counts.get(status, 0))

    filters = st.columns(3)
    platforms = filters[0].multiselect("Platform", sorted(table["Platform"].unique()), key="mt_platform")
    markets = filters[1].multiselect("Market", sorted(table["Market"].unique()), key="mt_market")
    statuses = filters[2].multiselect(
        "Status", [STATUS_AHEAD, STATUS_ON_TRACK, STATUS_AT_RISK, STATUS_UNAVAILABLE], key="mt_status"
    )
    view = table
    if platforms:
        view = view[view["Platform"].isin(platforms)]
    if markets:
        view = view[view["Market"].isin(markets)]
    if statuses:
        view = view[view["Goal status"].isin(statuses)]

    compact = [
        "Campaign",
        "Platform",
        "Market",
        "Objective",
        "Budget",
        "Spend",
        "Days remaining",
        "Result type",
        "Results",
        "Results goal",
        "Forecast attainment",
        "CPM",
        "Cost per result",
        "Result rate",
        "Goal status",
    ]
    show_table(view[compact], MARKET_FORMATS, "Goal status")
    with st.expander("More campaign detail"):
        detail = ["Campaign", "Market", "Pacing", "Campaign status", "Impressions", "Clicks", "Currency"]
        show_table(view[detail], MARKET_FORMATS)
    st.caption(
        f"Status uses forecast attainment of the results goal: Ahead of goal at {thresholds.ahead:.0%} or more, "
        f"On track at {thresholds.on_track:.0%} or more, otherwise At risk. "
        "Forecast unavailable means a goal, flight dates or results were not provided. "
        "Different result types are never compared."
    )
    return view


def _highlight(label: str, row: pd.Series | None, name_column: str, metric: str, fmt) -> None:
    if row is None:
        st.metric(label, "Not enough comparable data")
        return
    st.metric(label, str(row[name_column]))
    st.caption(f"{row['Platform']} - {metric}: {fmt(row)}")


def render_audience_creative(frame: pd.DataFrame, currency: str) -> dict:
    """Audience and creative comparisons using only compatible metrics."""
    found: dict = {"audience_cost": None, "audience_engaging": None, "creative_cost": None, "creative_engaging": None}
    audience_rank = rank_dimension(frame, "audience")
    creative_rank = rank_dimension(frame, "creative")
    if audience_rank.empty and creative_rank.empty:
        st.info(
            "Audience and creative names were not found in the loaded files, or delivery was too small to compare. "
            "Export at ad set / ad group and ad level to enable this view."
        )
        return found

    families = sorted(set(comparable_result_families(audience_rank)) | set(comparable_result_families(creative_rank)))
    family = None
    if len(families) > 1:
        family = st.selectbox(
            "Compare cost per result for",
            families,
            format_func=lambda key: RESULT_FAMILIES.get(key, key),
            help="Costs are only compared within the same result type.",
        )
    elif families:
        family = families[0]

    platforms = sorted(
        set(audience_rank.get("Platform", pd.Series(dtype=str))) | set(creative_rank.get("Platform", pd.Series(dtype=str)))
    )
    platform = None
    if len(platforms) > 1:
        platform = st.selectbox(
            "Compare engagement rate within",
            platforms,
            help="Each platform counts engagement differently, so engagement is only compared within one platform.",
        )
    elif platforms:
        platform = platforms[0]

    cost_fmt = lambda row: money(row["Cost per result"], row["Currency"], 3) + " per result"  # noqa: E731
    eng_fmt = lambda row: rate_pct(row["Engagement rate"])  # noqa: E731

    columns = st.columns(2)
    with columns[0]:
        st.markdown("**Audiences**")
        found["audience_cost"] = best_cost_effective(audience_rank, family)
        found["audience_engaging"] = best_engaging(audience_rank, platform)
        _highlight("Most cost-effective audience", found["audience_cost"], "Audience", "cost", cost_fmt)
        _highlight("Most engaging audience", found["audience_engaging"], "Audience", "engagement rate", eng_fmt)
    with columns[1]:
        st.markdown("**Creatives**")
        found["creative_cost"] = best_cost_effective(creative_rank, family)
        found["creative_engaging"] = best_engaging(creative_rank, platform)
        _highlight("Most cost-effective creative", found["creative_cost"], "Creative", "cost", cost_fmt)
        _highlight("Most engaging creative", found["creative_engaging"], "Creative", "engagement rate", eng_fmt)

    tabs = st.tabs(["Audience detail", "Creative detail"])
    for tab, rank, name in zip(tabs, [audience_rank, creative_rank], ["Audience", "Creative"]):
        with tab:
            if rank.empty:
                st.caption(f"No {name.lower()} data found.")
                continue
            shown = rank.drop(columns=["family"]).sort_values(["Platform", "Result type", "Cost per result"], na_position="last")
            show_table(
                shown,
                {
                    "Spend": "{:,.2f}",
                    "Impressions": "{:,.0f}",
                    "Results": "{:,.0f}",
                    "Engagements": "{:,.0f}",
                    "Cost per result": "{:,.3f}",
                    "Result rate": "{:.2%}",
                    "Engagement rate": "{:.2%}",
                },
            )
    st.caption(
        "Rows with fewer than 1,000 impressions are left out so tiny samples do not look like winners. "
        "Cost per result is only compared within one result type, and engagement only within one platform."
    )
    return found

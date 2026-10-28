"""Streamlit pieces for importing and showing paid media (advertising) reports."""

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
    aggregate_kpis,
    cpc,
    cpm,
    rate_pct,
    results_by_type,
)
from lollie.paid.schema import (
    CANONICAL_FIELDS,
    FIELD_LABELS,
    PLATFORM_OPTIONS,
    PLATFORM_OTHER,
    PLATFORM_WAVO,
)

PAID_HEADER_HINTS = ("campaign", "spend", "cost", "amount_spent", "impressions", "date", "day")
UPLOAD_TYPES = ["csv", "xlsx", "xls"]



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
                suggested = suggest_mapping(columns)
                detected = detect_platform(columns, uploaded.name)
                if detected == PLATFORM_OTHER and suggested.get("platform") and suggested.get("campaign_name"):
                    detected = PLATFORM_WAVO
                platform = st.selectbox(
                    "Report source",
                    PLATFORM_OPTIONS,
                    index=PLATFORM_OPTIONS.index(detected),
                    key=f"{key}_source",
                    help="Detected from the file name and column headings. Change it if it is wrong.",
                )
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
                        key=f"{key}_field_{name}",
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
            st.caption(f"{uploaded.name}: {len(result.frame):,} rows read.")
            for issue in result.issues:
                if issue.level in ("error", "warning"):
                    st.warning(f"{uploaded.name}: {issue.message}") if issue.level == "warning" else st.error(
                        f"{uploaded.name}: {issue.message}"
                    )
    frame, combine_issues = combine_paid_frames(results)
    issues = [issue for result in results for issue in result.issues if issue.level == "info"] + combine_issues
    return PaidData(frame=frame, issues=issues, results=results)



def show_table(frame: pd.DataFrame, formats: dict[str, str]) -> None:
    """Show a formatted table, falling back to plain formatting if pandas Styler is unavailable."""
    formats = {key: value for key, value in formats.items() if key in frame.columns}
    try:
        st.dataframe(frame.style.format(formats, na_rep="n/a"), width="stretch", hide_index=True)
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


def render_kpis(frame: pd.DataFrame, currency: str) -> dict:
    """Compact paid media KPIs. Everything shown is added up from the rows of one currency."""
    kpis = aggregate_kpis(frame)
    first = st.columns(6)
    first[0].metric("Spend", money(kpis["spend"], currency))
    first[1].metric("Impressions", number(kpis["impressions"]))
    first[2].metric("Views", number(kpis["views"]))
    first[3].metric("Engagements", number(kpis["engagements"]))
    first[4].metric("Clicks", number(kpis["clicks"]))
    first[5].metric("Landing page views", number(kpis["landing_page_views"]))
    second = st.columns(6)
    second[0].metric("Budget", money(kpis["budget"], currency))
    second[1].metric("CPM", money(kpis["cpm"], currency, 2))
    second[2].metric("CPC", money(kpis["cpc"], currency, 2))
    second[3].metric("CTR", rate_pct(kpis["ctr"]))
    return kpis


def render_results(frame: pd.DataFrame, currency: str) -> pd.DataFrame:
    """Results and cost per result, kept separate for each result definition."""
    table = results_by_type(frame)
    if table.empty:
        st.caption("No campaign results were reported, so cost per result and goal attainment are not available.")
        return table
    shown = table.drop(columns=["family"]).copy()
    shown["Goal attainment"] = [
        (results / goal if goal else None) for results, goal in zip(shown["Results"], shown["Goal"])
    ]
    if len(shown) > 1:
        st.caption(
            "Results are listed separately for each result type. Video views, landing page views and clicks are different "
            "things, so they are never added together or compared on one cost per result."
        )
    show_table(
        shown[["Result type", "Results", "Goal", "Goal attainment", "Spend", "Cost per result"]],
        {"Results": "{:,.0f}", "Goal": "{:,.0f}", "Goal attainment": "{:.0%}", "Spend": "{:,.2f}", "Cost per result": "{:,.3f}"},
    )
    return table


def by_country_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Paid media totals per country (rows that could not be tied to a country are shown as typed)."""
    if frame.empty:
        return pd.DataFrame()
    rows = []
    for market, group in frame.groupby("market", dropna=False):
        spend = group["spend"].sum() if group["spend"].notna().any() else None
        impressions = group["impressions"].sum() if group["impressions"].notna().any() else None
        clicks = group["clicks"].sum() if group["clicks"].notna().any() else None
        lpv = group["landing_page_views"].sum() if group["landing_page_views"].notna().any() else None
        rows.append(
            {
                "Country": market,
                "Spend": spend,
                "Impressions": impressions,
                "Clicks": clicks,
                "Landing page views": lpv,
                "CPM": cpm(spend, impressions),
                "CPC": cpc(spend, clicks),
            }
        )
    return pd.DataFrame(rows).sort_values("Spend", ascending=False, na_position="last").reset_index(drop=True)

"""Plain, factual campaign summary. It reports what the data shows and what it cannot show."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from lollie.analysis.baseline import WindowAnalysis
from lollie.analysis.markets import PAID
from lollie.analysis.relationships import Relationship

SECTION_ORDER = ["Advertising", "Streaming", "Markets", "Timing", "Data limitations"]


@dataclass
class Summary:
    sections: dict[str, list[str]] = field(default_factory=dict)

    def to_markdown(self, title: str = "") -> str:
        lines = [f"### {title}", ""] if title else []
        for name in SECTION_ORDER:
            items = self.sections.get(name) or []
            if not items:
                continue
            lines.append(f"**{name}**")
            lines.extend(f"- {item}" for item in items)
            lines.append("")
        return "\n".join(lines).strip() + "\n"


def _money(value: float | None, currency: str, digits: int = 0) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(currency)
    return f"{symbol}{value:,.{digits}f}" if symbol else f"{value:,.{digits}f} {currency}"


def _num(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:,.0f}"


def _pct(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:+.0%}"


def build_summary(
    *,
    campaign: str,
    scope_label: str,
    currency: str,
    kpis: dict,
    results_text: list[str],
    analysis: WindowAnalysis | None,
    market_table: pd.DataFrame,
    rank_note: str | None,
    relationship: Relationship | None,
    overlap_notes: list[str],
    data_notes: list[str],
    dates_note: str = "",
    source_attributed_present: bool = False,
    membership_verified: bool = True,
    multi_track: bool = False,
) -> Summary:
    summary = Summary({name: [] for name in SECTION_ORDER})

    ads = summary.sections["Advertising"]
    ads.append(
        f"Campaign '{campaign}' spent {_money(kpis.get('spend'), currency)} and delivered {_num(kpis.get('impressions'))} impressions, "
        f"{_num(kpis.get('clicks'))} clicks"
        + (f" and {_num(kpis.get('landing_page_views'))} landing page views" if kpis.get("landing_page_views") else "")
        + "."
    )
    if kpis.get("cpm") is not None:
        cpc = f" and CPC was {_money(kpis['cpc'], currency, 2)}" if kpis.get("cpc") is not None else ""
        ads.append(f"CPM was {_money(kpis['cpm'], currency, 2)}{cpc}.")
    ads.extend(results_text)

    streaming = summary.sections["Streaming"]
    if analysis is None or not analysis.usable:
        streaming.append(
            "A before / during comparison is not available for this selection"
            + (f": {analysis.method_text}" if analysis is not None and analysis.method_text else ".")
        )
    else:
        streaming.append(
            f"For {scope_label}, average daily streams were {_num(analysis.baseline.average)} before the campaign, "
            f"{_num(analysis.during.average)} during it"
            + (f" and {_num(analysis.post.average)} in the {analysis.post.days_in_window} days after." if analysis.post.average is not None else ".")
        )
        streaming.append(
            f"During the campaign, streams were {_num(analysis.during_actual)} against {_num(analysis.during_expected)} expected from the "
            f"baseline: an observed change of {_num(analysis.observed_change)} streams ({_pct(analysis.pct_change)}) versus baseline."
        )
        if analysis.post_pct_change is not None:
            streaming.append(f"In the period after the campaign, streams were {_pct(analysis.post_pct_change)} versus the same baseline.")
        streaming.append(f"Expected baseline method: {analysis.method.lower()}. {analysis.method_text}")

    markets = summary.sections["Markets"]
    if not market_table.empty:
        with_data = market_table[(market_table["Paid activity"] == PAID) & market_table["Change vs baseline"].notna()]
        positive = with_data[with_data["Change vs baseline"] >= 0.10]
        limited = with_data[with_data["Change vs baseline"] < 0.10]
        if not with_data.empty:
            markets.append(
                f"Higher than baseline (10% or more) in {len(positive)} of {len(with_data)} paid countries"
                + (": " + ", ".join(positive["Market"].head(6)) + "." if not positive.empty else ".")
            )
            if not limited.empty:
                markets.append(
                    "Limited or negative change (under 10%) in: "
                    + ", ".join(f"{row['Market']} ({_pct(row['Change vs baseline'])})" for _, row in limited.head(6).iterrows())
                    + "."
                )
        no_stream = market_table[(market_table["Paid activity"] == PAID) & market_table["Change vs baseline"].isna()]
        if not no_stream.empty:
            markets.append("Paid countries without a usable streaming comparison: " + ", ".join(no_stream["Market"].head(8)) + ".")
        if rank_note:
            markets.append(rank_note)

    timing = summary.sections["Timing"]
    if relationship is not None and relationship.label != "Not enough data":
        timing.append(
            f"Spend and streaming change: {relationship.label.lower()} (correlation {relationship.correlation:+.2f} across "
            f"{relationship.paired_days} days). {relationship.note}".strip()
        )
    elif relationship is not None and relationship.note:
        timing.append(relationship.note)
    timing.extend(overlap_notes)

    limits = summary.sections["Data limitations"]
    if dates_note:
        limits.append(dates_note)
    if analysis is not None:
        limits.extend(analysis.flags)
    limits.extend(data_notes)
    if multi_track and not membership_verified:
        limits.append("Playlist or multi-track membership has not been marked as verified.")
    if source_attributed_present:
        limits.append(
            "Playlist / source-attributed streams were loaded but are shown separately. Totals above use total track streams only."
        )
    limits.append(
        "This is an observational comparison with a before-campaign baseline. It does not show that the advertising caused the "
        "change; releases, playlisting, social posts, press and seasonality can move streams at the same time."
    )
    return summary


# Optional Estimated Streaming Value Change (Spotify-only; never part of the baseline).
DEFAULT_RATE_USD = 0.004
RATE_DSP = "Spotify"
LABEL = "Estimated Streaming Value Change"
NOT_CALCULATED = "Not calculated"

TOOLTIP = (
    "Observed Streaming Change x an assumed value per stream (default $0.004 USD per Spotify stream; editable under "
    "Advanced Settings). It is a rough planning estimate, not WMG revenue, royalty income, profit or advertising ROI. "
    "Spotify has no universal fixed per-stream royalty, the rate is applied to Spotify streams only, and the change "
    "is not shown to have been caused by advertising. A negative number is not a verified loss."
)


@dataclass
class StreamingValue:
    enabled: bool
    rate: float | None
    streams_change: float | None
    value: float | None
    display: str
    reason: str = ""

    @property
    def calculated(self) -> bool:
        return self.value is not None


def format_money(value: float) -> str:
    sign = "+" if value > 0 else ("-" if value < 0 else "")
    digits = 0 if abs(value) >= 1000 else 2
    return f"{sign}${abs(value):,.{digits}f}"


def estimate_streaming_value(
    observed_change: float | None,
    rate: float | None = DEFAULT_RATE_USD,
    *,
    enabled: bool = True,
    applies: bool = True,
    reason_if_not_applicable: str = "",
) -> StreamingValue:
    """Observed streaming change on Spotify x assumed rate. Not used in expected-streams baseline."""
    if not enabled:
        return StreamingValue(False, rate, observed_change, None, "Off")
    if not applies:
        reason = reason_if_not_applicable or "This estimate is not available for the current view."
        return StreamingValue(True, rate, observed_change, None, reason, reason)
    if rate is None or pd.isna(rate) or rate <= 0:
        reason = "No valid value per stream is set in Advanced Settings."
        return StreamingValue(True, rate, observed_change, None, reason, reason)
    if observed_change is None or pd.isna(observed_change):
        reason = "There is no valid observed streaming change for Spotify in the campaign window."
        return StreamingValue(True, rate, observed_change, None, reason, reason)
    value = float(observed_change) * float(rate)
    return StreamingValue(True, float(rate), float(observed_change), value, format_money(value))

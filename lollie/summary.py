"""Plain, factual campaign summary. It reports what the data shows and what it cannot show."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from lollie.analysis.baseline import WindowAnalysis
from lollie.analysis.catalog_model import NORMAL_VARIATION, NOT_ASSESSED, SLIGHTLY_ABOVE, SLIGHTLY_BELOW
from lollie.analysis.markets import PAID
from lollie.analysis.relationships import Relationship
from lollie.valuation import LABEL as VALUE_LABEL, StreamingValue

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


def describe_change(analysis: WindowAnalysis, period: str = "during") -> str | None:
    """One careful sentence: how streaming compared with the historical baseline, and whether that is unusual for this recording."""
    if period == "during":
        pct, assessed, label = analysis.pct_change, analysis.assessment, "during the campaign"
    else:
        pct, assessed = analysis.post_pct_change, analysis.post_assessment
        label = f"in the {analysis.post.days_in_window} days after the campaign"
    if pct is None or assessed is None or assessed.status == NOT_ASSESSED:
        return None
    if abs(pct) < 0.005:
        head = f"Streaming performance was in line with the historical baseline {label}."
    else:
        head = f"Streaming performance was {abs(pct):.1%} {'above' if pct > 0 else 'below'} the historical baseline {label}."
    swing = f"typically about \u00b1{assessed.typical_swing:.1%} for a period this long" if assessed.typical_swing is not None else ""
    if assessed.status == NORMAL_VARIATION:
        tail = f" That is within this recording's normal variation ({swing})." if swing else ""
    elif assessed.status in (SLIGHTLY_ABOVE, SLIGHTLY_BELOW):
        tail = f" That is at the edge of this recording's normal variation ({swing})." if swing else ""
    else:
        tail = f" That is larger than this recording's normal variation ({swing})." if swing else ""
    return head + tail


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
    value: StreamingValue | None = None,
    events: list[tuple[pd.Timestamp, str]] | None = None,
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
        sentence = describe_change(analysis)
        streaming.append(
            (sentence + " " if sentence else "")
            + f"Streams were {_num(analysis.during_actual)} against {_num(analysis.during_expected)} expected from the baseline: "
            f"an observed change of {_num(analysis.observed_change)} streams ({_pct(analysis.pct_change)})."
        )
        post_sentence = describe_change(analysis, "post")
        if post_sentence:
            streaming.append(post_sentence)
        streaming.append(f"Expected baseline: {analysis.method_text}")
        if value is not None and value.enabled:
            if value.calculated:
                streaming.append(
                    f"{VALUE_LABEL}: {value.display}, from {value.streams_change:+,.0f} observed Spotify streams at an assumed "
                    f"${value.rate:g} per stream. This is a planning estimate, not WMG revenue, royalty income, profit or advertising ROI, "
                    "and it does not show that the campaign caused the change."
                )
            else:
                streaming.append(f"{VALUE_LABEL}: not calculated. {value.reason}".strip())

    markets = summary.sections["Markets"]
    if not market_table.empty:
        with_data = market_table[(market_table["Paid activity"] == PAID) & market_table["Change vs baseline"].notna()]
        if not with_data.empty:
            above = with_data[with_data["Reading"].str.startswith("Above")]
            below = with_data[with_data["Reading"].str.startswith("Below")]
            other = with_data[~with_data.index.isin(above.index.union(below.index))]
            markets.append(
                f"Above the historical baseline and outside normal variation in {len(above)} of {len(with_data)} paid countries"
                + (": " + ", ".join(f"{row['Market']} ({_pct(row['Change vs baseline'])})" for _, row in above.head(6).iterrows()) + "." if not above.empty else ".")
            )
            if not below.empty:
                markets.append(
                    "Below the historical baseline and outside normal variation in: "
                    + ", ".join(f"{row['Market']} ({_pct(row['Change vs baseline'])})" for _, row in below.head(6).iterrows())
                    + "."
                )
            if not other.empty:
                markets.append(
                    "Within normal variation (or borderline) in: "
                    + ", ".join(f"{row['Market']} ({_pct(row['Change vs baseline'])})" for _, row in other.head(6).iterrows())
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
    if analysis is not None and events:
        window_end = analysis.post.end if analysis.post.days_in_window else analysis.end
        inside = [(d, label) for d, label in events if analysis.start <= d <= window_end]
        if inside:
            timing.append(
                "Events marked on the chart during the campaign or after it: "
                + "; ".join(f"{label} ({d:%b %d})" for d, label in inside[:5])
                + ". Streaming change in this period may reflect them as well as the advertising."
            )
    if analysis is not None:
        timing.extend(analysis.context)

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
        "This is an observational comparison with the recording's own pre-campaign history. It does not show that the advertising "
        "caused the change; releases, playlist placements, tours, anniversaries, social posts, press and seasonality can move "
        "streams at the same time."
    )
    return summary

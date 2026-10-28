"""Factual in-flight campaign recap generated only from imported data.

No explanations, causes or outcomes are invented. Anything not present in the
data is stated as unavailable.
"""

from __future__ import annotations

import pandas as pd

from lollie.paid.metrics import (
    STATUS_AHEAD,
    STATUS_AT_RISK,
    STATUS_ON_TRACK,
    pacing_label,
)


def _n(value, digits: int = 0) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:,.{digits}f}"


def _money(value, currency: str) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(currency)
    return f"{symbol}{value:,.0f}" if symbol else f"{value:,.0f} {currency}"


def _best_line(label: str, row: pd.Series | None, name_col: str, metric: str, fmt) -> str:
    if row is None:
        return f"- {label}: not enough comparable data."
    return f"- {label}: {row[name_col]} ({row['Platform']}; {fmt(row[metric])})"


def build_recap(
    *,
    artist: str,
    release: str,
    campaign_id: str,
    kpis: dict,
    currency: str,
    platforms: list[str],
    pacing: float | None,
    market_table: pd.DataFrame,
    as_of: pd.Timestamp,
    best_audience_cost: pd.Series | None = None,
    best_audience_engaging: pd.Series | None = None,
    best_creative_cost: pd.Series | None = None,
    streaming: dict | None = None,
) -> str:
    lines = [
        f"CAMPAIGN UPDATE: {artist} - {release}",
        f"Campaign ID: {campaign_id} | Data through {as_of:%B %d, %Y}",
        "",
        "DELIVERY",
        f"- Platforms: {', '.join(platforms) if platforms else 'n/a'}",
        f"- Impressions: {_n(kpis.get('impressions'))}",
        f"- Views: {_n(kpis.get('views'))}",
        f"- Engagements: {_n(kpis.get('engagements'))}",
        f"- Clicks: {_n(kpis.get('clicks'))}",
        f"- Spend: {_money(kpis.get('spend'), currency)}"
        + (f" of {_money(kpis['budget'], currency)} budget" if kpis.get("budget") else ""),
    ]
    if kpis.get("cpm") is not None:
        lines.append(f"- CPM: {kpis['cpm']:,.2f} {currency}")
    if kpis.get("cpc") is not None:
        lines.append(f"- CPC: {kpis['cpc']:,.2f} {currency}")
    if kpis.get("ctr") is not None:
        lines.append(f"- CTR: {kpis['ctr'] * 100:.2f}%")

    lines += ["", "PACING"]
    if pacing is None:
        lines.append("- Budget pacing: unavailable (needs budget and flight dates).")
    else:
        lines.append(f"- Budget pacing: {pacing * 100:.0f}% of planned spend to date ({pacing_label(pacing).lower()}).")

    lines += ["", "MARKETS"]
    if market_table.empty:
        lines.append("- No market-level data.")
    else:
        def names(status: str) -> str:
            subset = market_table[market_table["Goal status"] == status]
            labels = sorted({f"{r['Market']} ({r['Campaign']})" for _, r in subset.iterrows()})
            return ", ".join(labels) if labels else "none"

        lines.append(f"- Ahead of goal: {names(STATUS_AHEAD)}")
        lines.append(f"- On track: {names(STATUS_ON_TRACK)}")
        lines.append(f"- At risk: {names(STATUS_AT_RISK)}")
        unavailable = int((market_table["Goal status"] == "Forecast unavailable").sum())
        if unavailable:
            lines.append(f"- Forecast unavailable for {unavailable} campaign-market row(s) (missing goal, dates or results).")

    lines += ["", "AUDIENCES AND CREATIVES"]
    def cost_text(row: pd.Series | None):
        suffix = f" ({row['Result type']})" if row is not None else ""
        return lambda v: f"{v:,.2f} {currency} per result{suffix}"

    lines.append(_best_line("Most cost-effective audience", best_audience_cost, "Audience", "Cost per result", cost_text(best_audience_cost)))
    lines.append(_best_line("Most engaging audience", best_audience_engaging, "Audience", "Engagement rate", lambda v: f"{v * 100:.2f}% engagement rate"))
    lines.append(_best_line("Best-performing creative", best_creative_cost, "Creative", "Cost per result", cost_text(best_creative_cost)))

    lines += ["", "STREAMING"]
    if not streaming:
        lines.append("- No streaming data loaded.")
    else:
        pct = streaming.get("lift_percent")
        lines.append(
            f"- In the {streaming['window']} after the post, actual streams were {_n(streaming['actual'])} "
            f"vs a modeled baseline of {_n(streaming['expected'])} "
            f"({'n/a' if pct is None else f'{pct:+.1f}%'})."
        )
        lines.append("- This is an observational comparison, not proof that advertising or the post caused the change.")
    return "\n".join(lines)

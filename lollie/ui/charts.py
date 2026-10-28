"""Plotly charts for the Lollie V2 dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from lollie.analysis.baseline import WindowAnalysis, trend_line

TEAL = "#00a8b8"
TEAL_DARK = "#008a99"
TEAL_SOFT = "rgba(0, 168, 184, 0.45)"
GREEN = "rgba(46, 184, 114, 0.30)"
GRAY = "#7a8793"
FONT = dict(family="Helvetica Neue, Arial, sans-serif")


def _py(ts) -> object:
    return pd.Timestamp(ts).to_pydatetime()


def streaming_intelligence_chart(
    analysis: WindowAnalysis,
    *,
    title: str,
    spend_daily: pd.DataFrame | None = None,
    currency: str = "USD",
    organic_posts: list[tuple[pd.Timestamp, str]] | None = None,
    impact_days: int = 2,
    show_trend: bool = True,
    view_range: tuple[pd.Timestamp, pd.Timestamp] | None = None,
) -> go.Figure:
    """Actual vs expected streams (top) with daily ad spend on the same dates (bottom)."""
    frame = analysis.series
    has_spend = spend_daily is not None and not spend_daily.empty
    start, end = analysis.start, analysis.end
    figure = make_subplots(
        rows=2 if has_spend else 1,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.07,
        row_heights=[0.7, 0.3] if has_spend else [1.0],
    )

    expected = frame[frame["expected"].notna()]
    if not expected.empty:
        figure.add_trace(
            go.Scatter(
                x=expected["date"], y=expected["expected"], mode="lines", name="Expected baseline streams",
                line=dict(color=GRAY, width=2, dash="dash"),
                hovertemplate="Expected: %{y:,.0f}<extra></extra>",
            ),
            row=1, col=1,
        )
    figure.add_trace(
        go.Scatter(
            x=frame["date"], y=frame["actual"], mode="lines", name="Actual streams", connectgaps=False,
            line=dict(color=TEAL, width=3), hovertemplate="Actual: %{y:,.0f}<extra></extra>",
        ),
        row=1, col=1,
    )
    if show_trend:
        trend = trend_line(frame.set_index("date")["actual"])
        figure.add_trace(
            go.Scatter(
                x=trend.index, y=trend.values, mode="lines", name="7-day trend",
                line=dict(color=TEAL_DARK, width=1.5, dash="dot"), hovertemplate="7-day trend: %{y:,.0f}<extra></extra>",
            ),
            row=1, col=1,
        )

    after = frame[(frame["window"].isin(["During", "After"])) & frame["actual"].notna() & frame["expected"].notna()]
    if not after.empty:
        figure.add_trace(
            go.Scatter(
                x=pd.concat([after["date"], after["date"][::-1]]),
                y=pd.concat([after["actual"], after["expected"][::-1]]),
                fill="toself", name="Actual minus expected", fillcolor=GREEN, line=dict(width=0), hoverinfo="skip",
            ),
            row=1, col=1,
        )

    base = analysis.baseline
    for x0, x1, color, label in (
        (base.start, base.end + pd.Timedelta(days=1), "rgba(122,135,147,0.07)", "Baseline window"),
        (start, end + pd.Timedelta(days=1), "rgba(0,168,184,0.10)", "Campaign"),
    ):
        figure.add_vrect(
            x0=_py(x0), x1=_py(x1), fillcolor=color, line_width=0, layer="below",
            annotation_text=label, annotation_position="top left", annotation_font_size=11, row=1, col=1,
        )
    if analysis.post.days_in_window:
        figure.add_vrect(
            x0=_py(analysis.post.start), x1=_py(analysis.post.end + pd.Timedelta(days=1)),
            fillcolor="rgba(46,184,114,0.06)", line_width=0, layer="below",
            annotation_text="After campaign", annotation_position="top left", annotation_font_size=11, row=1, col=1,
        )
    for moment, label in ((start, "Campaign start"), (end + pd.Timedelta(days=1), "Campaign end")):
        figure.add_vline(
            x=_py(moment), line_width=2, line_dash="dash", line_color=TEAL_DARK,
            annotation_text=label, annotation_position="top", annotation_font_size=11, row=1, col=1,
        )

    chart_min, chart_max = frame["date"].min(), frame["date"].max() + pd.Timedelta(days=1)
    for moment, label in organic_posts or []:
        if chart_min <= moment <= chart_max:
            figure.add_vline(
                x=_py(moment), line_width=2, line_dash="dot", line_color="#e08a00",
                annotation_text=label, annotation_position="bottom", annotation_font_size=10, row=1, col=1,
            )
            if impact_days > 0:
                figure.add_vrect(
                    x0=_py(moment), x1=_py(moment + pd.Timedelta(days=impact_days)),
                    fillcolor="rgba(224,138,0,0.10)", line_width=0, layer="below", row=1, col=1,
                )

    if has_spend:
        spend = spend_daily[(spend_daily["date"] >= chart_min) & (spend_daily["date"] <= chart_max)]
        figure.add_trace(
            go.Bar(
                x=spend["date"], y=spend["spend"], name=f"Daily ad spend ({currency})", marker=dict(color=TEAL_SOFT),
                hovertemplate="Ad spend: %{y:,.2f} " + currency + "<extra></extra>",
            ),
            row=2, col=1,
        )
        figure.update_yaxes(title_text=f"Ad spend ({currency})", row=2, col=1)

    figure.update_yaxes(title_text="Daily streams", row=1, col=1)
    figure.update_xaxes(title_text="Date", row=2 if has_spend else 1, col=1)
    if view_range:
        figure.update_xaxes(range=[_py(view_range[0]), _py(view_range[1] + pd.Timedelta(days=1))])
    figure.update_layout(
        title=title, hovermode="x unified", template="plotly_white", font=FONT,
        height=720 if has_spend else 560, margin=dict(l=40, r=40, t=130, b=40), bargap=0.15,
        legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="left", x=0),
    )
    return figure


def market_chart(table: pd.DataFrame) -> go.Figure:
    """Ad spend and observed streaming change for the same countries, side by side."""
    shown = table.head(12).iloc[::-1]
    figure = make_subplots(
        rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.04,
        subplot_titles=("Ad spend", "Streaming change vs baseline (during campaign)"),
    )
    figure.add_trace(
        go.Bar(
            y=shown["Market"], x=shown["Ad spend"].fillna(0), orientation="h", marker=dict(color=TEAL_SOFT), name="Ad spend",
            hovertemplate="%{y}: %{x:,.0f}<extra></extra>",
        ),
        row=1, col=1,
    )
    change = shown["Change vs baseline"]
    colors = []
    for value, activity in zip(change, shown["Paid activity"]):
        if pd.isna(value):
            colors.append("rgba(0,0,0,0)")
        elif activity != "Paid":
            colors.append("#c9d1d6")
        else:
            colors.append(TEAL if value >= 0.10 else GRAY)
    figure.add_trace(
        go.Bar(
            y=shown["Market"], x=change * 100, orientation="h", marker=dict(color=colors), name="Change vs baseline",
            hovertemplate="%{y}: %{x:+.1f}%<extra></extra>", text=[("n/a" if pd.isna(v) else f"{v:+.0%}") for v in change],
            textposition="outside",
        ),
        row=1, col=2,
    )
    top = float(change.max()) * 100 if change.notna().any() else 10.0
    bottom = min(float(change.min()) * 100, 0.0) if change.notna().any() else 0.0
    figure.update_xaxes(title_text="Spend", row=1, col=1)
    figure.update_xaxes(title_text="% vs baseline", ticksuffix="%", range=[bottom * 1.3, max(top, 5.0) * 1.3], row=1, col=2)
    figure.update_layout(
        template="plotly_white", font=FONT, showlegend=False, height=max(320, 60 * len(shown) + 120),
        margin=dict(l=40, r=60, t=60, b=40),
    )
    return figure

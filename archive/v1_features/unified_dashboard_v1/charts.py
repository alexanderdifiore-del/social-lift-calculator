"""Plotly charts for the unified Lollie dashboard.

The streaming chart keeps the original expected-vs-actual layout and adds
optional overlays (paid flights and daily spend, organic posts, commerce).
Overlays use only data that was actually loaded; nothing is interpolated.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from lollie.commerce import CommerceOverlay
from lollie.streaming import granularity_label

TEAL = "#00a8b8"
TEAL_SOFT = "rgba(0, 168, 184, 0.45)"
TEAL_STRONG = "rgba(0, 168, 184, 0.90)"
GREEN_SOFT = "rgba(46, 184, 114, 0.85)"
FLIGHT_FILL = "rgba(0, 168, 184, 0.07)"

FONT = dict(family="Helvetica Neue, Arial, sans-serif")


def _py(ts) -> object:
    return pd.Timestamp(ts).to_pydatetime()


def summary_bar_chart(expected: float, actual: float, lift: float, unit_label: str = "Streams") -> go.Figure:
    values = [expected, actual, lift]
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=["Expected Baseline", "Actual Streams", "Estimated Social Lift"],
            y=values,
            text=[f"{value:,.0f}" for value in values],
            textposition="outside",
            marker=dict(
                color=[TEAL_SOFT, TEAL_STRONG, GREEN_SOFT],
                line=dict(color="rgba(0,0,0,0.15)", width=1),
            ),
        )
    )
    figure.update_layout(
        title="Campaign Performance Summary",
        xaxis_title="Metric",
        yaxis_title=unit_label,
        template="plotly_white",
        height=420,
        margin=dict(l=40, r=40, t=70, b=40),
        font=FONT,
    )
    return figure


def commerce_bar_chart(by_product: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=by_product["Product Category"],
            y=by_product["Gross Revenue"],
            name="Gross Revenue",
            text=[f"${value:,.0f}" for value in by_product["Gross Revenue"]],
            textposition="outside",
            marker=dict(color=TEAL_STRONG, line=dict(color="rgba(0,0,0,0.15)", width=1)),
        )
    )
    figure.add_trace(
        go.Bar(
            x=by_product["Product Category"],
            y=by_product["Estimated Net Revenue"],
            name="Estimated Net Revenue",
            text=[f"${value:,.0f}" for value in by_product["Estimated Net Revenue"]],
            textposition="outside",
            marker=dict(color=GREEN_SOFT, line=dict(color="rgba(0,0,0,0.15)", width=1)),
        )
    )
    figure.update_layout(
        title="Attributed Product Revenue by Category",
        xaxis_title="Product Category",
        yaxis_title="Revenue ($)",
        barmode="group",
        template="plotly_white",
        height=500,
        margin=dict(l=40, r=40, t=80, b=120),
        font=FONT,
        legend_title="Revenue Type",
    )
    return figure


def merge_flights(flights: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Union of overlapping campaign flights, for one shaded band on the chart."""
    if flights is None or flights.empty:
        return []
    spans = sorted(zip(flights["start"], flights["end"]))
    merged: list[list[pd.Timestamp]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def streaming_chart(
    *,
    df: pd.DataFrame,
    impact_mask: pd.Series,
    granularity: str,
    post_timestamp,
    impact_end,
    impact_window_hours: int,
    song_title: str,
    extra_posts: list[tuple[object, str]] | None = None,
    commerce: CommerceOverlay | None = None,
    show_commerce_baseline: bool = True,
    commerce_baseline_percent: float = 35.0,
    paid_daily: pd.DataFrame | None = None,
    paid_flights: pd.DataFrame | None = None,
    paid_currency: str = "USD",
    paid_estimate_note: str = "",
) -> go.Figure:
    has_commerce = commerce is not None and not commerce.is_empty
    has_paid = paid_daily is not None and not paid_daily.empty

    chart_start = df["timestamp"].min()
    chart_end = df["timestamp"].max() + (pd.Timedelta(days=1) if granularity == "daily" else pd.Timedelta(hours=1))

    if has_paid:
        paid_daily = paid_daily[
            (paid_daily["date"] >= chart_start.normalize()) & (paid_daily["date"] <= chart_end)
        ]
        has_paid = not paid_daily.empty

    rows = 2 if has_paid else 1
    figure = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.74, 0.26] if rows == 2 else [1.0],
        specs=[[{"secondary_y": True}]] + ([[{"secondary_y": False}]] if rows == 2 else []),
    )

    figure.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["expected_baseline_streams"],
            mode="lines",
            name="Expected Baseline Streams",
            line=dict(width=2),
            hovertemplate="Time: %{x}<br>Expected: %{y:,.0f}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["actual_streams"],
            mode="lines",
            name="Actual Streams",
            line=dict(width=3),
            hovertemplate="Time: %{x}<br>Actual: %{y:,.0f}<extra></extra>",
        ),
        row=1,
        col=1,
    )

    lift_df = df.loc[impact_mask]
    if not lift_df.empty:
        figure.add_trace(
            go.Scatter(
                x=pd.concat([lift_df["timestamp"], lift_df["timestamp"][::-1]]),
                y=pd.concat([lift_df["actual_streams"], lift_df["expected_baseline_streams"][::-1]]),
                fill="toself",
                name="Observed difference vs. baseline (modeled lift)",
                opacity=0.25,
                line=dict(width=0),
                hoverinfo="skip",
            ),
            row=1,
            col=1,
        )

    if has_paid:
        spans = merge_flights(paid_flights)
        if spans:
            figure.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    marker=dict(size=10, color=TEAL, symbol="square", opacity=0.35),
                    name="Paid flight window",
                    hoverinfo="skip",
                ),
                row=1,
                col=1,
            )
            for start, end in spans:
                figure.add_vrect(
                    x0=_py(max(start, chart_start.normalize())),
                    x1=_py(min(end, chart_end)),
                    fillcolor=TEAL,
                    opacity=0.07,
                    line_width=0,
                    layer="below",
                    row=1,
                    col=1,
                )
        figure.add_trace(
            go.Bar(
                x=paid_daily["date"],
                y=paid_daily["spend"],
                name=f"Daily paid spend ({paid_currency})",
                marker=dict(color=TEAL_SOFT),
                hovertemplate="Date: %{x|%b %d}<br>Spend: %{y:,.2f} " + paid_currency + "<extra></extra>",
            ),
            row=2,
            col=1,
        )
        figure.update_yaxes(title_text=f"Spend ({paid_currency})", row=2, col=1)

    figure.add_vline(
        x=_py(post_timestamp),
        line_width=2,
        line_dash="dash",
        annotation_text="Social Post Goes Live",
        annotation_position="top",
        row=1,
        col=1,
    )
    figure.add_vrect(
        x0=_py(post_timestamp),
        x1=_py(impact_end),
        fillcolor="gray",
        opacity=0.08,
        line_width=0,
        annotation_text=f"{impact_window_hours}h Impact Window",
        annotation_position="top left",
        row=1,
        col=1,
    )

    for timestamp, label in extra_posts or []:
        figure.add_vline(
            x=_py(timestamp),
            line_width=2,
            line_dash="dot",
            annotation_text=label,
            annotation_position="top",
            row=1,
            col=1,
        )

    if has_commerce:
        frame = commerce.frame
        if show_commerce_baseline:
            figure.add_trace(
                go.Scatter(
                    x=frame["timestamp"],
                    y=frame["cumulative_commerce_value"] * (commerce_baseline_percent / 100),
                    mode="lines",
                    name="Expected Product Revenue Baseline",
                    line=dict(width=2, dash="dash"),
                    hovertemplate=(
                        "Date: %{x}<br>Expected Commerce Baseline: "
                        + commerce.prefix
                        + "%{y:,.0f}"
                        + commerce.suffix
                        + "<extra></extra>"
                    ),
                ),
                row=1,
                col=1,
                secondary_y=True,
            )
        figure.add_trace(
            go.Scatter(
                x=frame["timestamp"],
                y=frame["cumulative_commerce_value"],
                mode="lines+markers",
                name="Attributed Product Revenue",
                line=dict(width=3),
                hovertemplate=(
                    "Date: %{x}<br>"
                    + commerce.label
                    + ": "
                    + commerce.prefix
                    + "%{y:,.0f}"
                    + commerce.suffix
                    + "<extra></extra>"
                ),
            ),
            row=1,
            col=1,
            secondary_y=True,
        )
        figure.update_yaxes(title_text=commerce.axis_title, showgrid=False, row=1, col=1, secondary_y=True)
    else:
        figure.update_yaxes(visible=False, row=1, col=1, secondary_y=True)

    figure.update_yaxes(title_text=granularity_label(granularity), row=1, col=1, secondary_y=False)
    figure.update_xaxes(title_text="Date / Time", row=rows, col=1)
    figure.update_xaxes(range=[_py(chart_start), _py(chart_end)])

    title = f"{song_title} Streaming Trend: Expected vs Actual"
    if paid_estimate_note:
        title += f"<br><sup>{paid_estimate_note}</sup>"
    figure.update_layout(
        title=title,
        legend_title="Chart Labels",
        hovermode="x unified",
        template="plotly_white",
        height=675 if rows == 1 else 780,
        margin=dict(l=40, r=40, t=80, b=40),
        font=FONT,
        bargap=0.15,
    )
    return figure

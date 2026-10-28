"""Commerce revenue model (original Lollie calculations, extracted unchanged)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

PRODUCT_CATALOG = {
    "Vinyl LP": {"price": 29.99, "cost": 11.00, "units": 120, "conversion": 0.025, "fees": 8.0},
    "Limited Color Vinyl": {"price": 34.99, "cost": 13.00, "units": 80, "conversion": 0.018, "fees": 8.0},
    "CD": {"price": 14.99, "cost": 4.00, "units": 95, "conversion": 0.015, "fees": 7.0},
    "Cassette": {"price": 12.99, "cost": 3.50, "units": 40, "conversion": 0.008, "fees": 7.0},
    "Deluxe Edition / Box Set": {"price": 89.99, "cost": 35.00, "units": 25, "conversion": 0.004, "fees": 9.0},
    "Signed Physical Product": {"price": 49.99, "cost": 18.00, "units": 35, "conversion": 0.006, "fees": 8.0},
    "Artist Apparel": {"price": 35.00, "cost": 12.00, "units": 150, "conversion": 0.030, "fees": 10.0},
    "Accessories": {"price": 18.00, "cost": 6.00, "units": 100, "conversion": 0.020, "fees": 10.0},
    "Poster / Print": {"price": 25.00, "cost": 7.00, "units": 60, "conversion": 0.012, "fees": 8.0},
    "Merch Bundle": {"price": 65.00, "cost": 25.00, "units": 45, "conversion": 0.007, "fees": 9.0},
    "Digital Album / Download": {"price": 10.99, "cost": 1.00, "units": 75, "conversion": 0.018, "fees": 15.0},
    "Fan Club / Membership": {"price": 9.99, "cost": 1.50, "units": 50, "conversion": 0.010, "fees": 12.0},
    "Ticket / VIP Upsell": {"price": 75.00, "cost": 25.00, "units": 30, "conversion": 0.005, "fees": 10.0},
}

COMMERCE_COLUMNS = [
    "Sale Date",
    "Product Category",
    "Attributed Units",
    "Average Selling Price",
    "Unit Cost / COGS",
    "Fee Rate (%)",
    "Source",
]


@dataclass
class CommerceModel:
    detail: pd.DataFrame = field(default_factory=pd.DataFrame)
    by_product: pd.DataFrame = field(default_factory=pd.DataFrame)
    daily: pd.DataFrame = field(default_factory=pd.DataFrame)
    units: float = 0.0
    gross_revenue: float = 0.0
    net_revenue: float = 0.0
    revenue_per_1k_social_views: float = 0.0
    revenue_per_lift_stream: float = 0.0

    @property
    def is_empty(self) -> bool:
        return self.by_product.empty


def build_commerce_model(
    rows: list[dict],
    social_reach: float,
    social_lift_streams: float,
) -> CommerceModel:
    """Gross revenue, COGS, fees, net revenue and margins by product and date."""
    if not rows:
        return CommerceModel()

    detail = pd.DataFrame(rows)
    detail["Sale Date"] = pd.to_datetime(detail["Sale Date"], errors="coerce")
    for column in ["Attributed Units", "Average Selling Price", "Unit Cost / COGS", "Fee Rate (%)"]:
        detail[column] = pd.to_numeric(detail[column], errors="coerce").fillna(0)
    detail = detail.dropna(subset=["Sale Date"])
    if detail.empty:
        return CommerceModel()

    detail["Gross Revenue"] = detail["Attributed Units"] * detail["Average Selling Price"]
    detail["Total COGS"] = detail["Attributed Units"] * detail["Unit Cost / COGS"]
    detail["Fees / Discounts"] = detail["Gross Revenue"] * (detail["Fee Rate (%)"] / 100)
    detail["Estimated Net Revenue"] = (
        detail["Gross Revenue"] - detail["Total COGS"] - detail["Fees / Discounts"]
    )
    detail["Estimated Margin (%)"] = np.where(
        detail["Gross Revenue"] > 0,
        detail["Estimated Net Revenue"] / detail["Gross Revenue"] * 100,
        0,
    )

    by_product = detail.groupby("Product Category", as_index=False).agg(
        {
            "Attributed Units": "sum",
            "Average Selling Price": "mean",
            "Unit Cost / COGS": "mean",
            "Fee Rate (%)": "mean",
            "Gross Revenue": "sum",
            "Total COGS": "sum",
            "Fees / Discounts": "sum",
            "Estimated Net Revenue": "sum",
        }
    )
    by_product["Estimated Margin (%)"] = np.where(
        by_product["Gross Revenue"] > 0,
        by_product["Estimated Net Revenue"] / by_product["Gross Revenue"] * 100,
        0,
    )

    daily = detail.groupby("Sale Date", as_index=False).agg(
        {"Attributed Units": "sum", "Gross Revenue": "sum", "Estimated Net Revenue": "sum"}
    ).rename(columns={"Sale Date": "timestamp"})

    gross = float(detail["Gross Revenue"].sum())
    return CommerceModel(
        detail=detail,
        by_product=by_product,
        daily=daily,
        units=float(detail["Attributed Units"].sum()),
        gross_revenue=gross,
        net_revenue=float(detail["Estimated Net Revenue"].sum()),
        revenue_per_1k_social_views=gross / (social_reach / 1000) if social_reach > 0 else 0.0,
        revenue_per_lift_stream=gross / social_lift_streams if social_lift_streams > 0 else 0.0,
    )


OVERLAY_METRICS = {
    "Gross Product Revenue": {
        "column": "Gross Revenue",
        "label": "Gross Product Revenue",
        "axis": "Product Revenue ($)",
        "prefix": "$",
        "suffix": "",
    },
    "Estimated Net Revenue": {
        "column": "Estimated Net Revenue",
        "label": "Net Product Revenue",
        "axis": "Product Revenue ($)",
        "prefix": "$",
        "suffix": "",
    },
    "Attributed Units Sold": {
        "column": "Attributed Units",
        "label": "Attributed Units Sold",
        "axis": "Attributed Product Units",
        "prefix": "",
        "suffix": " units",
    },
}


@dataclass
class CommerceOverlay:
    frame: pd.DataFrame = field(default_factory=pd.DataFrame)
    label: str = ""
    axis_title: str = ""
    prefix: str = ""
    suffix: str = ""
    projected: bool = False

    @property
    def is_empty(self) -> bool:
        return self.frame.empty


def build_commerce_overlay(
    model: CommerceModel,
    metric: str,
    post_timestamp,
    window_days: int,
    chart_start,
    *,
    allow_projection: bool,
) -> CommerceOverlay:
    """Cumulative commerce line for the streaming chart.

    Dated sales inside the window are plotted as reported. Only when
    ``allow_projection`` is true (simulated / auto-estimate data) and no dated
    sale falls in the window is the total spread over the window with a decay
    curve, as in the original Lollie chart.
    """
    if model.is_empty:
        return CommerceOverlay()
    spec = OVERLAY_METRICS[metric]
    column = spec["column"]
    total = {
        "Gross Revenue": model.gross_revenue,
        "Estimated Net Revenue": model.net_revenue,
        "Attributed Units": model.units,
    }[column]

    overlay = CommerceOverlay(
        label=spec["label"],
        axis_title=spec["axis"],
        prefix=spec["prefix"],
        suffix=spec["suffix"],
    )

    post_timestamp = pd.Timestamp(post_timestamp)
    window_end = post_timestamp + pd.Timedelta(days=window_days)
    in_window = model.daily.copy()
    in_window["timestamp"] = pd.to_datetime(in_window["timestamp"], errors="coerce")
    in_window = in_window[
        (in_window["timestamp"] >= post_timestamp) & (in_window["timestamp"] < window_end)
    ].sort_values("timestamp")

    if not in_window.empty:
        start_row = pd.DataFrame(
            {
                "timestamp": [chart_start],
                "Attributed Units": [0],
                "Gross Revenue": [0],
                "Estimated Net Revenue": [0],
            }
        )
        in_window = pd.concat([start_row, in_window], ignore_index=True).sort_values("timestamp")
        in_window["commerce_value"] = in_window[column]
        in_window["cumulative_commerce_value"] = in_window["commerce_value"].cumsum()
        overlay.frame = in_window.reset_index(drop=True)
        return overlay

    if allow_projection and total > 0:
        dates = [post_timestamp + pd.Timedelta(days=day) for day in range(window_days)]
        weights = np.exp(-np.linspace(0, 2.4, window_days))
        weights = weights / weights.sum()
        values = total * weights
        overlay.frame = pd.DataFrame(
            {
                "timestamp": dates,
                "commerce_value": values,
                "cumulative_commerce_value": np.cumsum(values),
            }
        )
        overlay.projected = True
        overlay.label = "Projected " + spec["label"]
    return overlay

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

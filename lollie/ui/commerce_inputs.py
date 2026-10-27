"""Sidebar controls for the commerce module (original Lollie controls, plus Excel upload)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

import pandas as pd
import streamlit as st

from lollie.commerce import PRODUCT_CATALOG
from lollie.imports.file_loader import guess_column, load_tabular_upload

DATA_MODE_AUTO = "Auto estimate from product categories"
DATA_MODE_MANUAL = "Manual dated sales entries"
DATA_MODE_UPLOAD = "Commerce CSV / Excel upload"

COMMERCE_HEADER_HINTS = ("date", "product", "units", "price", "sale", "revenue")


@dataclass
class CommerceInputs:
    enabled: bool = True
    show_overlay: bool = True
    overlay_window_days: int = 7
    overlay_metric: str = "Gross Product Revenue"
    show_baseline: bool = True
    baseline_percent: float = 35.0
    data_mode: str = DATA_MODE_UPLOAD
    rows: list[dict] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    @property
    def is_estimate(self) -> bool:
        return self.data_mode == DATA_MODE_AUTO


def _rows_from_upload(frame: pd.DataFrame, columns: dict[str, str | None]) -> list[dict]:
    rows: list[dict] = []
    for _, row in frame.iterrows():
        sale_date = pd.to_datetime(row[columns["date"]], errors="coerce")
        if pd.isna(sale_date):
            continue
        units = pd.to_numeric(row[columns["units"]], errors="coerce")
        price = pd.to_numeric(row[columns["price"]], errors="coerce")
        if pd.isna(units) or pd.isna(price):
            continue
        cost = pd.to_numeric(row[columns["cost"]], errors="coerce") if columns["cost"] else 0
        fee = pd.to_numeric(row[columns["fee"]], errors="coerce") if columns["fee"] else 0
        rows.append(
            {
                "Sale Date": sale_date.date(),
                "Product Category": str(row[columns["product"]]),
                "Attributed Units": int(units),
                "Average Selling Price": float(price),
                "Unit Cost / COGS": 0.0 if pd.isna(cost) else float(cost),
                "Fee Rate (%)": 0.0 if pd.isna(fee) else float(fee),
                "Source": "File upload",
            }
        )
    return rows


def render_commerce_sidebar(*, demo_mode: bool, post_timestamp, social_reach: float) -> CommerceInputs:
    sidebar = st.sidebar
    sidebar.markdown("---")
    sidebar.subheader("Commerce / Product Revenue")

    inputs = CommerceInputs()
    inputs.enabled = sidebar.checkbox(
        "Enable Commerce Revenue Tracking",
        value=True,
        help="Show product revenue associated with the social/streaming impact window.",
    )
    inputs.show_overlay = sidebar.checkbox(
        "Show Commerce Overlay on Streaming Chart",
        value=True,
        help="Overlay product revenue or product sales onto the streaming trend chart.",
    )
    inputs.overlay_window_days = sidebar.selectbox(
        "Commerce Overlay Window",
        [7, 14],
        index=0,
        help="How far after the social post to show commerce impact.",
    )
    inputs.overlay_metric = sidebar.selectbox(
        "Commerce Overlay Metric",
        ["Gross Product Revenue", "Estimated Net Revenue", "Attributed Units Sold"],
        help="Choose what commerce metric should appear on the streaming trend chart.",
    )
    inputs.show_baseline = sidebar.checkbox(
        "Show Commerce Baseline Line",
        value=True,
        help="Show an estimated baseline for product revenue or units without the social/streaming spike.",
    )
    inputs.baseline_percent = sidebar.slider(
        "Commerce Baseline Share (%)",
        min_value=0.0,
        max_value=100.0,
        value=35.0,
        step=5.0,
        help="Estimate what percentage of the commerce result may have happened without the social/streaming spike.",
    )

    modes = [DATA_MODE_AUTO, DATA_MODE_MANUAL, DATA_MODE_UPLOAD] if demo_mode else [DATA_MODE_UPLOAD, DATA_MODE_MANUAL]
    inputs.data_mode = sidebar.radio(
        "Commerce Data Mode",
        modes,
        key=f"commerce_mode_{'demo' if demo_mode else 'live'}",
        help="Upload a sales export, or type dated sales by product."
        + (" Auto estimate is a demo-only simulation." if demo_mode else ""),
    )

    if not inputs.enabled:
        return inputs

    catalog = PRODUCT_CATALOG
    if inputs.data_mode == DATA_MODE_AUTO:
        method = sidebar.selectbox(
            "Revenue Attribution Method",
            ["Manual attributed units", "Estimate from social reach"],
            help="Manual mode lets you type units sold. Estimate mode calculates units from social reach and purchase conversion assumptions.",
        )
        selected = sidebar.multiselect(
            "Product Categories",
            list(catalog.keys()),
            default=["Vinyl LP", "CD", "Artist Apparel", "Merch Bundle"],
            help="Select the product categories you want to include in the revenue model.",
        )
        for index, product in enumerate(selected):
            defaults = catalog[product]
            with sidebar.expander(product, expanded=False):
                price = st.number_input(
                    f"{product} Avg Selling Price ($)", min_value=0.0, value=float(defaults["price"]), step=1.0, key=f"auto_price_{index}"
                )
                cost = st.number_input(
                    f"{product} Unit Cost / COGS ($)", min_value=0.0, value=float(defaults["cost"]), step=1.0, key=f"auto_cost_{index}"
                )
                fee = st.slider(
                    f"{product} Fees / Discounts (%)",
                    min_value=0.0,
                    max_value=50.0,
                    value=float(defaults["fees"]),
                    step=0.5,
                    key=f"auto_fees_{index}",
                )
                if method == "Manual attributed units":
                    units = st.number_input(
                        f"{product} Attributed Units Sold", min_value=0, value=int(defaults["units"]), step=1, key=f"auto_units_{index}"
                    )
                else:
                    conversion = st.number_input(
                        f"{product} Purchase Conversion Rate (%)",
                        min_value=0.0,
                        max_value=10.0,
                        value=float(defaults["conversion"]),
                        step=0.001,
                        format="%.3f",
                        key=f"auto_conversion_{index}",
                    )
                    units = int(round(social_reach * (conversion / 100)))
                    st.caption(f"Estimated units: {units:,}")
                inputs.rows.append(
                    {
                        "Sale Date": post_timestamp.date(),
                        "Product Category": product,
                        "Attributed Units": units,
                        "Average Selling Price": price,
                        "Unit Cost / COGS": cost,
                        "Fee Rate (%)": fee,
                        "Source": "Auto estimate (demo)",
                    }
                )

    elif inputs.data_mode == DATA_MODE_MANUAL:
        count = sidebar.number_input(
            "Number of Sales Rows", min_value=1, max_value=25, value=3 if not demo_mode else 5, step=1,
            help="Add dated sales rows by product category.",
        )
        products = list(catalog.keys())
        for row_index in range(int(count)):
            with sidebar.expander(f"Sales Row {row_index + 1}", expanded=row_index == 0):
                sale_date = st.date_input(
                    "Sale Date",
                    value=(post_timestamp + timedelta(days=row_index)).date(),
                    key=f"manual_sale_date_{row_index}",
                )
                product = st.selectbox(
                    "Product Category", products, index=row_index % len(products), key=f"manual_product_{row_index}"
                )
                defaults = catalog[product]
                units = st.number_input(
                    "Units Sold",
                    min_value=0,
                    value=int(defaults["units"] / 4) if demo_mode else 0,
                    step=1,
                    key=f"manual_units_{'demo' if demo_mode else 'live'}_{row_index}",
                )
                price = st.number_input(
                    "Average Selling Price ($)", min_value=0.0, value=float(defaults["price"]), step=1.0, key=f"manual_price_{row_index}"
                )
                cost = st.number_input(
                    "Unit Cost / COGS ($)", min_value=0.0, value=float(defaults["cost"]), step=1.0, key=f"manual_cost_{row_index}"
                )
                fee = st.slider(
                    "Fees / Discounts (%)",
                    min_value=0.0,
                    max_value=50.0,
                    value=float(defaults["fees"]),
                    step=0.5,
                    key=f"manual_fee_{row_index}",
                )
                if units > 0 or demo_mode:
                    inputs.rows.append(
                        {
                            "Sale Date": sale_date,
                            "Product Category": product,
                            "Attributed Units": units,
                            "Average Selling Price": price,
                            "Unit Cost / COGS": cost,
                            "Fee Rate (%)": fee,
                            "Source": "Manual entry",
                        }
                    )

    else:
        uploaded = sidebar.file_uploader(
            "Upload Commerce CSV / Excel",
            type=["csv", "xlsx", "xls"],
            key="commerce_csv_file",
            help="A file with date, product, units, price and (optionally) cost and fee columns.",
        )
        with sidebar.expander("Commerce file format example"):
            st.code(
                """sale_date,product_category,units_sold,average_selling_price,unit_cost,fee_rate
2026-06-17,Vinyl LP,45,29.99,11.00,8
2026-06-18,Artist Apparel,32,35.00,12.00,10
2026-06-19,Deluxe Edition / Box Set,8,89.99,35.00,9""",
                language="csv",
            )
        if uploaded is not None:
            try:
                frame = load_tabular_upload(uploaded, header_hints=COMMERCE_HEADER_HINTS)
            except Exception:  # noqa: BLE001
                sidebar.error("The commerce file could not be read. Try exporting it again as CSV or Excel.")
                frame = pd.DataFrame()
            if not frame.empty:
                sidebar.success("Commerce file uploaded.")
                with sidebar.expander("Preview commerce file"):
                    st.dataframe(frame.head(10), width="stretch")
                columns = list(frame.columns)
                optional = ["Use default / zero"] + columns

                def pick(label: str, keywords: list[str], fallback: int, options: list[str]) -> str:
                    guess = guess_column(columns, keywords)
                    index = options.index(guess) if guess in options else min(fallback, len(options) - 1)
                    return sidebar.selectbox(label, options, index=index)

                date_col = pick("Select sale date column", ["sale_date", "date", "day"], 0, columns)
                product_col = pick("Select product column", ["product", "item", "sku", "category"], 1, columns)
                units_col = pick("Select units sold column", ["units", "quantity", "qty"], 2, columns)
                price_col = pick("Select average selling price column", ["price", "asp"], 3, columns)
                cost_col = pick("Select unit cost / COGS column", ["cost", "cogs"], 0, optional)
                fee_col = pick("Select fee / discount rate column", ["fee", "discount"], 0, optional)
                inputs.rows = _rows_from_upload(
                    frame,
                    {
                        "date": date_col,
                        "product": product_col,
                        "units": units_col,
                        "price": price_col,
                        "cost": None if cost_col == "Use default / zero" else cost_col,
                        "fee": None if fee_col == "Use default / zero" else fee_col,
                    },
                )
                if not inputs.rows:
                    inputs.messages.append("No usable sales rows were found. Check the date, units and price column choices.")
    return inputs

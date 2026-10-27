import pandas as pd
import pytest

from lollie.commerce import PRODUCT_CATALOG, build_commerce_model


def _row(product, units, date="2026-10-27", source="Manual entry"):
    d = PRODUCT_CATALOG[product]
    return {
        "Sale Date": pd.Timestamp(date).date(),
        "Product Category": product,
        "Attributed Units": units,
        "Average Selling Price": d["price"],
        "Unit Cost / COGS": d["cost"],
        "Fee Rate (%)": d["fees"],
        "Source": source,
    }


def test_matches_original_default_commerce_numbers():
    rows = [_row(p, PRODUCT_CATALOG[p]["units"]) for p in ["Vinyl LP", "CD", "Artist Apparel", "Merch Bundle"]]
    model = build_commerce_model(rows, social_reach=850_000, social_lift_streams=83_350)
    assert round(model.gross_revenue) == 13_198
    assert round(model.net_revenue) == 7_397
    assert model.units == 410
    assert model.revenue_per_1k_social_views == pytest.approx(15.53, abs=0.01)


def test_line_item_gross_cogs_fees_margin():
    model = build_commerce_model([_row("Vinyl LP", 100)], 0, 0)
    line = model.detail.iloc[0]
    assert line["Gross Revenue"] == pytest.approx(2999.0)
    assert line["Total COGS"] == pytest.approx(1100.0)
    assert line["Fees / Discounts"] == pytest.approx(239.92)
    assert line["Estimated Net Revenue"] == pytest.approx(1659.08)
    assert line["Estimated Margin (%)"] == pytest.approx(55.32, abs=0.01)


def test_revenue_per_1k_views_only_when_reach_is_known():
    model = build_commerce_model([_row("CD", 10)], social_reach=0, social_lift_streams=0)
    assert model.revenue_per_1k_social_views == 0
    assert model.revenue_per_lift_stream == 0


def test_groups_by_product_and_date():
    rows = [_row("CD", 10, "2026-10-27"), _row("CD", 5, "2026-10-28"), _row("Poster / Print", 4, "2026-10-28")]
    model = build_commerce_model(rows, 1000, 100)
    cd = model.by_product.set_index("Product Category").loc["CD"]
    assert cd["Attributed Units"] == 15
    assert len(model.daily) == 2


def test_bad_dates_and_empty_input_are_safe():
    assert build_commerce_model([], 0, 0).is_empty
    bad = _row("CD", 10)
    bad["Sale Date"] = "not a date"
    assert build_commerce_model([bad], 0, 0).is_empty

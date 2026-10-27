import io

import pandas as pd
import pytest

from lollie.imports.file_loader import load_tabular_upload
from lollie.paid.ingest import (
    combine_paid_frames,
    detect_currency_from_header,
    detect_platform,
    file_fingerprint,
    normalize_paid_frame,
    suggest_mapping,
)
from lollie.paid.schema import (
    PLATFORM_GOOGLE,
    PLATFORM_META,
    PLATFORM_SNAP,
    PLATFORM_TIKTOK,
    PLATFORM_WAVO,
    canonical_platform,
    result_family,
)


class FakeUpload:
    def __init__(self, name, data: bytes):
        self.name = name
        self._data = data

    def getvalue(self):
        return self._data


META = pd.DataFrame(
    {
        "Day": ["2026-10-25", "2026-10-26", "2026-10-26"],
        "Campaign name": ["Release Push", "Release Push", "Total:"],
        "Ad set name": ["Lookalike", "Lookalike", ""],
        "Ad name": ["Reel A", "Reel A", ""],
        "Country": ["US", "US", ""],
        "Objective": ["Landing page views", "Landing page views", ""],
        "Amount spent (USD)": [100.0, 150.0, 250.0],
        "Impressions": [10000, 14000, 24000],
        "Link clicks": [150, 210, 360],
        "Results": [80, 120, 200],
    }
)
TIKTOK = pd.DataFrame(
    {
        "By Day": ["2026-10-25", "2026-10-26"],
        "Campaign name": ["Sound Push", "Sound Push"],
        "Ad group name": ["Interest A", "Interest A"],
        "Ad name": ["Studio 15s", "Studio 15s"],
        "Country/Region": ["US", "US"],
        "Objective type": ["Video views", "Video views"],
        "Cost": [60.0, 80.0],
        "Impression": [9000, 12000],
        "Click": [90, 100],
        "Video views": [4000, 5200],
        "Cost per result": [0.015, 0.0154],
    }
)
GOOGLE = pd.DataFrame(
    {
        "Day": ["2026-10-25"],
        "Campaign": ["YT Official Video"],
        "Ad group": ["Related channels"],
        "Country/Territory": ["MX"],
        "Cost": ["$1,234.50"],
        "Impr.": ["1,200,000"],
        "Clicks": [3000],
        "Views": [250000],
        "Interactions": [4000],
    }
)
SNAP = pd.DataFrame(
    {
        "Date": ["2026-10-25"],
        "Campaign": ["Snap Lens Push"],
        "Amount Spent": [500],
        "Impressions": [200000],
        "Swipe-Ups": [900],
        "Video Views": [60000],
    }
)


def test_platform_names_are_canonicalized():
    assert canonical_platform("Facebook / Instagram") == PLATFORM_META
    assert canonical_platform("tiktok") == PLATFORM_TIKTOK
    assert canonical_platform("YouTube Ads") == PLATFORM_GOOGLE
    assert canonical_platform("Snap") == PLATFORM_SNAP
    assert canonical_platform("WAVO") == PLATFORM_WAVO


@pytest.mark.parametrize(
    "frame,expected",
    [(META, PLATFORM_META), (TIKTOK, PLATFORM_TIKTOK), (GOOGLE, PLATFORM_GOOGLE), (SNAP, PLATFORM_SNAP)],
)
def test_each_platform_is_detected_and_mapped(frame, expected):
    assert detect_platform(list(frame.columns)) == expected
    mapping = suggest_mapping(list(frame.columns))
    for required in ("date", "campaign_name", "spend", "impressions"):
        assert mapping[required] is not None, required


def test_cost_per_result_column_is_never_mapped_as_spend_or_results():
    mapping = suggest_mapping(list(TIKTOK.columns))
    assert mapping["spend"] == "Cost"
    assert mapping["results"] is None


def test_meta_normalization_drops_total_row_and_reads_currency():
    mapping = suggest_mapping(list(META.columns))
    result = normalize_paid_frame(META, mapping, PLATFORM_META)
    assert len(result.frame) == 2
    assert result.frame["spend"].sum() == 250
    assert (result.frame["currency"] == "USD").all()
    assert any("total/summary" in i.message for i in result.issues)
    assert detect_currency_from_header("Amount spent (EUR)") == "EUR"


def test_numeric_cleaning_handles_symbols_and_commas():
    mapping = suggest_mapping(list(GOOGLE.columns))
    result = normalize_paid_frame(GOOGLE, mapping, PLATFORM_GOOGLE)
    row = result.frame.iloc[0]
    assert row["spend"] == 1234.50
    assert row["impressions"] == 1_200_000


def test_results_derived_from_matching_metric_for_video_objective():
    mapping = suggest_mapping(list(TIKTOK.columns))
    result = normalize_paid_frame(TIKTOK, mapping, PLATFORM_TIKTOK)
    assert result.frame["result_family"].eq("video_views").all()
    assert result.frame["results"].tolist() == [4000, 5200]


def test_landing_page_results_come_only_from_a_results_column():
    mapping = suggest_mapping(list(META.columns))
    mapping["results"] = None
    result = normalize_paid_frame(META, mapping, PLATFORM_META)
    assert result.frame["results"].isna().all()
    assert any("need a Results column" in i.message for i in result.issues)


def test_missing_spend_is_an_error_and_missing_currency_is_flagged():
    raw = pd.DataFrame({"Campaign": ["A"], "Impressions": [10]})
    result = normalize_paid_frame(raw, suggest_mapping(list(raw.columns)), PLATFORM_META)
    assert result.has_errors
    raw2 = pd.DataFrame({"Campaign": ["A"], "Spend": [10]})
    result2 = normalize_paid_frame(raw2, suggest_mapping(list(raw2.columns)), PLATFORM_META)
    assert any("assumed USD" in i.message for i in result2.issues)
    assert any("No usable date" in i.message for i in result2.issues)


def test_bad_numbers_and_clicks_over_impressions_are_flagged_not_hidden():
    raw = pd.DataFrame({"Campaign": ["A", "B"], "Spend": ["12", "oops"], "Impressions": [100, 100], "Clicks": [500, 1]})
    result = normalize_paid_frame(raw, suggest_mapping(list(raw.columns)), PLATFORM_META)
    messages = " ".join(i.message for i in result.issues)
    assert "not numbers" in messages
    assert "more clicks than impressions" in messages
    assert pd.isna(result.frame["spend"].iloc[1])


def test_same_file_uploaded_twice_is_counted_once():
    mapping = suggest_mapping(list(TIKTOK.columns))
    raw_bytes = TIKTOK.to_csv(index=False).encode()
    a = normalize_paid_frame(TIKTOK, mapping, PLATFORM_TIKTOK, source_label="a.csv")
    b = normalize_paid_frame(TIKTOK, mapping, PLATFORM_TIKTOK, source_label="b.csv")
    a.file_hash = b.file_hash = file_fingerprint(raw_bytes)
    combined, issues = combine_paid_frames([a, b])
    assert combined["spend"].sum() == 140
    assert any("identical" in i.message for i in issues)


def test_wavo_rows_duplicating_a_platform_export_are_not_double_counted():
    native = normalize_paid_frame(
        TIKTOK, suggest_mapping(list(TIKTOK.columns)), PLATFORM_TIKTOK, source_label="tiktok.csv"
    )
    wavo_raw = pd.DataFrame(
        {
            "Date": ["2026-10-25", "2026-10-26", "2026-10-26"],
            "Platform": ["TikTok", "TikTok", "Snapchat"],
            "Campaign": ["Sound Push", "Sound Push", "Snap Lens Push"],
            "Spend": [60.0, 80.0, 300.0],
            "Impressions": [9000, 12000, 100000],
        }
    )
    wavo = normalize_paid_frame(wavo_raw, suggest_mapping(list(wavo_raw.columns)), PLATFORM_WAVO, source_label="wavo.xlsx")
    combined, issues = combine_paid_frames([native, wavo])
    assert combined["spend"].sum() == 140 + 300
    tiktok_spend = combined.loc[combined["platform"] == PLATFORM_TIKTOK, "spend"].sum()
    assert tiktok_spend == 140
    assert any("lower-priority" in i.message for i in issues)


def test_multiple_currencies_are_flagged_and_not_merged():
    eur = pd.DataFrame({"Campaign": ["A"], "Spend": [10], "Currency": ["EUR"]})
    usd = pd.DataFrame({"Campaign": ["B"], "Spend": [10], "Currency": ["USD"]})
    results = [
        normalize_paid_frame(f, suggest_mapping(list(f.columns)), PLATFORM_META, source_label=name)
        for f, name in [(eur, "eur"), (usd, "usd")]
    ]
    combined, issues = combine_paid_frames(results)
    assert set(combined["currency"]) == {"EUR", "USD"}
    assert any("never combined" in i.message for i in issues)


def test_errored_files_are_excluded_from_the_combined_data():
    bad = pd.DataFrame({"Campaign": ["A"], "Impressions": [10]})
    result = normalize_paid_frame(bad, suggest_mapping(list(bad.columns)), PLATFORM_META)
    combined, _ = combine_paid_frames([result])
    assert combined.empty


def test_result_family_keeps_incompatible_objectives_apart():
    assert result_family("Landing page views") == "landing_page_views"
    assert result_family("Video views") == "video_views"
    assert result_family("Post engagement") == "engagements"
    assert result_family("Link clicks") == "clicks"
    assert result_family("Brand awareness") == "other"
    assert result_family(None) is None


def test_loader_reads_csv_with_title_rows_and_bom():
    text = "\ufeffCampaign performance\n2026-10-01 - 2026-10-31\nDay,Campaign,Cost,Impr.\n2026-10-25,A,10,1000\n"
    frame = load_tabular_upload(
        FakeUpload("google.csv", text.encode("utf-8")), header_hints=("campaign", "cost", "impr")
    )
    assert list(frame.columns) == ["Day", "Campaign", "Cost", "Impr."]
    assert len(frame) == 1


def test_loader_reads_excel_with_title_rows():
    buffer = io.BytesIO()
    sheet = pd.DataFrame(
        [["WAVO Report", None, None], ["Date", "Campaign", "Spend"], ["2026-10-25", "A", 10]]
    )
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        sheet.to_excel(writer, header=False, index=False)
    frame = load_tabular_upload(
        FakeUpload("wavo.xlsx", buffer.getvalue()), header_hints=("campaign", "spend")
    )
    assert list(frame.columns) == ["Date", "Campaign", "Spend"]
    assert frame["Spend"].iloc[0] == 10

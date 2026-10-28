"""Paid media report ingestion: column mapping, validation and de-duplication.

Supports exports from Meta Ads, TikTok Ads, Google Ads / YouTube, Snapchat Ads
and WAVO consolidated reporting. Nothing here invents data: missing metrics stay
missing and every assumption is reported back as an issue.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from lollie.geo import normalize_market
from lollie.paid.schema import (
    CANONICAL_FIELDS,
    DATE_FIELDS,
    FIELD_EXCLUDE,
    FIELD_PATTERNS,
    NUMERIC_FIELDS,
    PLATFORM_GOOGLE,
    PLATFORM_META,
    PLATFORM_OTHER,
    PLATFORM_SNAP,
    PLATFORM_TIKTOK,
    PLATFORM_WAVO,
    RESULT_SOURCE_COLUMN,
    SOURCE_PRIORITY,
    TEXT_FIELDS,
    canonical_platform,
    normalize_name,
    result_family,
)

TOTAL_ROW = re.compile(r"^\s*(total|grand total|all campaigns|subtotal)\b", re.IGNORECASE)


@dataclass
class Issue:
    level: str  # "error" | "warning" | "info"
    message: str


@dataclass
class IngestResult:
    frame: pd.DataFrame
    issues: list[Issue] = field(default_factory=list)
    source_label: str = ""
    platform: str = PLATFORM_OTHER
    file_hash: str = ""

    @property
    def has_errors(self) -> bool:
        return any(i.level == "error" for i in self.issues)


def file_fingerprint(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def suggest_mapping(columns: list[str]) -> dict[str, str | None]:
    """Auto-suggest a canonical field for each column (never reuses a column)."""
    normalized = {col: normalize_name(col) for col in columns}
    mapping: dict[str, str | None] = {fld: None for fld in CANONICAL_FIELDS}
    used: set[str] = set()

    for fld in CANONICAL_FIELDS:
        exclude = FIELD_EXCLUDE.get(fld)
        for pattern in FIELD_PATTERNS.get(fld, []):
            regex = re.compile(pattern)
            for col, norm in normalized.items():
                if col in used or (exclude and exclude.search(norm)):
                    continue
                if regex.fullmatch(norm):
                    mapping[fld] = col
                    used.add(col)
                    break
            if mapping[fld] is not None:
                break
    return mapping


def detect_platform(columns: list[str], filename: str = "") -> str:
    """Best-effort platform guess from filename, then column fingerprints."""
    by_name = canonical_platform(filename)
    if by_name != PLATFORM_OTHER:
        return by_name
    norm = {normalize_name(c) for c in columns}
    joined = " ".join(norm)
    if "swipe_ups" in norm or "swipes" in norm or "paid_impressions" in norm:
        return PLATFORM_SNAP
    if "stat_time_day" in norm or ("ad_group_name" in norm and "cost" in norm and "impression" in norm):
        return PLATFORM_TIKTOK
    if any(n.startswith("amount_spent") for n in norm) or "ad_set_name" in norm:
        return PLATFORM_META
    if "impr" in norm or "interactions" in norm or "avg_cpv" in joined:
        return PLATFORM_GOOGLE
    return PLATFORM_OTHER


def detect_currency_from_header(column_name: str | None) -> str | None:
    if not column_name:
        return None
    match = re.search(r"\(([A-Za-z]{3})\)", str(column_name))
    return match.group(1).upper() if match else None


def _clean_numeric(series: pd.Series) -> tuple[pd.Series, int]:
    """Coerce to numbers; returns series and the count of unparseable non-empty cells."""
    text = series.astype(str).str.strip()
    blank = series.isna() | text.isin(["", "nan", "None", "--", "-", "—"])
    cleaned = text.str.replace(r"[,$€£%\s]", "", regex=True)
    cleaned = cleaned.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    numbers = pd.to_numeric(cleaned, errors="coerce")
    bad = int((numbers.isna() & ~blank).sum())
    numbers[blank] = np.nan
    return numbers, bad


def normalize_paid_frame(
    raw: pd.DataFrame,
    mapping: dict[str, str | None],
    platform: str,
    *,
    default_currency: str = "USD",
    source_label: str = "",
) -> IngestResult:
    """Convert a raw platform export into the canonical paid-media frame."""
    issues: list[Issue] = []
    out = pd.DataFrame(index=raw.index)

    def column(fld: str) -> pd.Series | None:
        col = mapping.get(fld)
        if col and col in raw.columns:
            return raw[col]
        return None

    # --- numeric fields
    for fld in NUMERIC_FIELDS:
        series = column(fld)
        if series is None:
            out[fld] = np.nan
            continue
        numbers, bad = _clean_numeric(series)
        out[fld] = numbers
        if bad:
            issues.append(Issue("warning", f"{bad} value(s) in '{mapping[fld]}' were not numbers and were left blank."))

    # --- date fields
    for fld in DATE_FIELDS:
        series = column(fld)
        if series is None:
            out[fld] = pd.NaT
        else:
            out[fld] = pd.to_datetime(series.astype(str).str.replace("\n", " "), errors="coerce")

    # --- text fields
    for fld in TEXT_FIELDS:
        series = column(fld)
        if series is None:
            out[fld] = None
        else:
            text = series.astype("string").str.strip()
            text = text.mask(text.isin(["", "nan", "None", "<NA>"]))
            out[fld] = text.astype(object).where(text.notna(), None)

    # --- drop total / summary rows
    names = out["campaign_name"].fillna("").astype(str)
    total_mask = names.str.match(TOTAL_ROW)
    if total_mask.any():
        issues.append(Issue("info", f"Ignored {int(total_mask.sum())} total/summary row(s) so they are not double counted."))
        out = out.loc[~total_mask].copy()

    # --- platform
    if column("platform") is not None and out["platform"].notna().any():
        out["platform"] = out["platform"].map(lambda v: canonical_platform(v) if v else platform)
    else:
        out["platform"] = platform

    # --- currency
    header_currency = detect_currency_from_header(mapping.get("spend"))
    if column("currency") is not None and out["currency"].notna().any():
        out["currency"] = out["currency"].map(lambda v: str(v).upper() if v else default_currency)
    elif header_currency:
        out["currency"] = header_currency
        issues.append(Issue("info", f"Currency {header_currency} taken from the spend column header."))
    else:
        out["currency"] = default_currency
        if out["spend"].notna().any():
            issues.append(Issue("warning", f"No currency in file; assumed {default_currency}. Change it in import settings if wrong."))

    # --- objective / result family
    out["objective_family"] = out["objective"].map(result_family)
    out["result_family"] = out["result_type"].map(result_family)

    has_results_col = column("results") is not None
    if has_results_col:
        out["result_family"] = out["result_family"].fillna(out["objective_family"])
        unknown = out["results"].notna() & out["result_family"].isna()
        if unknown.any():
            out.loc[unknown, "result_family"] = "other"
            issues.append(Issue("warning", "Some results have no result type or objective; grouped as 'Other results' and not compared with other metrics."))
    else:
        out["results"] = np.nan
        derived_any = False
        for family, source_col in RESULT_SOURCE_COLUMN.items():
            rows = out["objective_family"] == family
            if rows.any() and out.loc[rows, source_col].notna().any():
                out.loc[rows, "results"] = out.loc[rows, source_col]
                out.loc[rows, "result_family"] = family
                derived_any = True
        if derived_any:
            issues.append(Issue("info", "Results derived from the matching metric column for each campaign objective (video views, clicks or engagements)."))
        unresolved = (out["objective_family"] == "landing_page_views") & out["results"].isna()
        if unresolved.any():
            issues.append(
                Issue(
                    "warning",
                    "Landing page view campaigns need a Results or Landing page views column; results are unavailable for those rows.",
                )
            )

    # --- validation
    if out["spend"].notna().sum() == 0:
        issues.append(Issue("error", "No spend column was mapped or found. Spend is required."))
    if out["date"].isna().all():
        issues.append(Issue("warning", "No usable date column. Totals and tables work, but time-series overlays are unavailable."))
    elif out["date"].isna().any():
        issues.append(Issue("warning", f"{int(out['date'].isna().sum())} row(s) have no valid date and are excluded from time-series views."))
    if out["campaign_name"].isna().all() and out["campaign_id"].isna().all():
        issues.append(Issue("warning", "No campaign name or ID mapped; rows are grouped under 'Unnamed campaign'."))
    for fld in ("spend", "impressions", "clicks", "views", "engagements", "results"):
        negatives = int((out[fld] < 0).sum())
        if negatives:
            issues.append(Issue("warning", f"{negatives} negative value(s) in {fld}; check for refunds or credits in the export."))
    over = int((out["clicks"] > out["impressions"]).sum())
    if over:
        issues.append(Issue("warning", f"{over} row(s) report more clicks than impressions; verify the column mapping."))

    out["campaign_name"] = out["campaign_name"].fillna(out["campaign_id"]).fillna("Unnamed campaign")
    codes, labels = [], []
    unmatched: set[str] = set()
    for raw_market in out["market"]:
        code, label = normalize_market(raw_market)
        codes.append(code)
        labels.append(label)
        if code is None:
            unmatched.add(label)
    out["market_code"] = codes
    out["market"] = labels
    if unmatched:
        issues.append(
            Issue(
                "warning",
                "These market labels were not recognized as countries and were kept as typed: "
                + ", ".join(sorted(unmatched)[:10])
                + ". They cannot be matched to streaming countries.",
            )
        )
    if column("market") is None:
        issues.append(Issue("info", "No country / market column mapped; rows are treated as 'All markets' and cannot be matched to a streaming country."))
    out["source_file"] = source_label
    out["source_priority"] = out["platform"].map(SOURCE_PRIORITY).fillna(3).astype(int)
    out["reported_platform"] = platform
    if platform == PLATFORM_WAVO:
        out["source_priority"] = SOURCE_PRIORITY[PLATFORM_WAVO]

    return IngestResult(frame=out.reset_index(drop=True), issues=issues, source_label=source_label, platform=platform)


def combine_paid_frames(results: list[IngestResult]) -> tuple[pd.DataFrame, list[Issue]]:
    """Merge several imports without double counting the same campaign-day.

    * The same file uploaded twice is dropped.
    * When a consolidated (WAVO) report repeats campaign-days that a
      platform-native export already covers, the lower-priority rows are removed.
    * Different currencies are kept separate (never summed together).
    """
    issues: list[Issue] = []
    usable: list[IngestResult] = []
    seen_hashes: set[str] = set()
    for result in results:
        if result.has_errors or result.frame.empty:
            continue
        if result.file_hash and result.file_hash in seen_hashes:
            issues.append(Issue("warning", f"'{result.source_label}' is identical to a file already imported and was skipped."))
            continue
        if result.file_hash:
            seen_hashes.add(result.file_hash)
        usable.append(result)

    if not usable:
        return pd.DataFrame(columns=CANONICAL_FIELDS), issues

    combined = pd.concat([r.frame for r in usable], ignore_index=True)
    combined["_key_date"] = combined["date"].dt.normalize()
    combined["_overlap_key"] = list(
        zip(combined["platform"], combined["campaign_name"].str.lower(), combined["_key_date"].astype(str))
    )

    priorities = combined.groupby("_overlap_key")["source_priority"].transform("min")
    lower = combined["source_priority"] > priorities
    if lower.any():
        removed = int(lower.sum())
        issues.append(
            Issue(
                "info",
                f"Removed {removed} row(s) from lower-priority sources (e.g. WAVO) that duplicate campaign-days already in a platform export.",
            )
        )
        combined = combined.loc[~lower]

    combined = combined.drop(columns=["_key_date", "_overlap_key"]).reset_index(drop=True)

    if combined["currency"].nunique() > 1:
        issues.append(Issue("warning", "Multiple currencies found (" + ", ".join(sorted(combined["currency"].unique())) + "). Totals are shown per currency and never combined."))
    return combined, issues

"""Dashboard metrics and warnings for promotional credits."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from lollie.credits.settings import WarningSettings


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def compute_credit_balances(row: dict[str, Any]) -> dict[str, float]:
    """Derive used / remaining from ledger-aware summary fields."""
    issued = float(row.get("original_issued_amount") or 0)
    applied = float(row.get("applied_total") or 0)
    reserved = float(row.get("reserved_total") or 0)
    remaining = max(issued - applied, 0)
    return {
        "issued": issued,
        "applied": applied,
        "reserved": reserved,
        "remaining": remaining,
    }


def build_inventory_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    records = []
    for row in rows:
        balances = compute_credit_balances(row)
        records.append(
            {
                "Platform": row["platform"],
                "Account": row["ad_account_id"],
                "Artist": row.get("artist") or "",
                "Campaign": row.get("campaign") or "",
                "Market": row.get("market") or "",
                "Credit Type": row["credit_category"],
                "Promotion": row["promotion_name"],
                "Issued Amount": balances["issued"],
                "Used Amount": balances["applied"],
                "Remaining Balance": balances["remaining"],
                "Currency": row["currency"],
                "Expiration": row.get("expiration_date") or "",
                "Status": row["credit_status"],
                "Verification": row.get("verification_source") or "",
                "Manual / Unreconciled": bool(row.get("is_manual_unreconciled")),
                "Demo": bool(row.get("is_demo")),
                "_credit_id": row["id"],
            }
        )
    return pd.DataFrame(records)


def summarize_by_currency(inventory: pd.DataFrame) -> pd.DataFrame:
    if inventory.empty:
        return pd.DataFrame(
            columns=[
                "Currency",
                "Total Issued",
                "Total Available",
                "Total Used",
                "Pending Qualification",
            ]
        )
    pending_statuses = {
        "pending_qualification",
        "pending_issuance",
        "awaiting_activation",
    }
    available_statuses = {
        "available",
        "reserved",
        "partially_applied",
    }

    def _sum(mask: pd.Series, column: str) -> float:
        return float(inventory.loc[mask, column].sum()) if mask.any() else 0.0

    rows = []
    for currency, group in inventory.groupby("Currency"):
        pending = group["Status"].isin(pending_statuses)
        available = group["Status"].isin(available_statuses)
        expired = group["Status"].isin({"expired", "forfeited"})
        rows.append(
            {
                "Currency": currency,
                "Total Issued": group["Issued Amount"].sum(),
                "Total Available": group.loc[available, "Remaining Balance"].sum(),
                "Total Used": group["Used Amount"].sum(),
                "Pending Qualification": group.loc[pending, "Issued Amount"].sum(),
                "Expired / Forfeited": group.loc[expired, "Remaining Balance"].sum(),
            }
        )
    return pd.DataFrame(rows)


def expiration_warnings(
    rows: list[dict[str, Any]],
    settings: WarningSettings,
    *,
    today: date | None = None,
) -> list[dict[str, str]]:
    today = today or date.today()
    warnings: list[dict[str, str]] = []
    for row in rows:
        exp = _parse_date(row.get("expiration_date"))
        balances = compute_credit_balances(row)
        remaining = balances["remaining"]
        promo = row.get("promotion_name", "Credit")
        platform = row.get("platform", "")

        if row.get("credit_status") in {"pending_qualification", "pending_issuance"}:
            warnings.append(
                {
                    "level": "info",
                    "message": f"{platform} — {promo}: pending qualification or issuance (not guaranteed).",
                }
            )
        if row.get("credit_status") == "awaiting_activation":
            warnings.append(
                {
                    "level": "info",
                    "message": f"{platform} — {promo}: awaiting activation per offer terms.",
                }
            )
        if row.get("is_manual_unreconciled"):
            warnings.append(
                {
                    "level": "warning",
                    "message": f"{platform} — {promo}: manually reported — reconcile with billing before finance use.",
                }
            )
        if exp and remaining > 0:
            days_left = (exp - today).days
            if days_left < 0:
                warnings.append(
                    {
                        "level": "error",
                        "message": f"{platform} — {promo}: expired with {remaining:,.2f} {row['currency']} unused.",
                    }
                )
            elif days_left <= settings.expiring_soon_days:
                warnings.append(
                    {
                        "level": "error",
                        "message": f"{platform} — {promo}: expires in {days_left} day(s); {remaining:,.2f} {row['currency']} remaining.",
                    }
                )
            elif days_left <= settings.expiring_warning_days:
                warnings.append(
                    {
                        "level": "warning",
                        "message": f"{platform} — {promo}: expires in {days_left} day(s).",
                    }
                )
        if row.get("eligible_campaigns"):
            warnings.append(
                {
                    "level": "info",
                    "message": f"{platform} — {promo}: restricted to specific campaigns — review eligibility.",
                }
            )
        if float(row.get("qualifying_spend_requirement") or 0) > 0 and row.get(
            "credit_status"
        ) in {"pending_qualification", "available"}:
            warnings.append(
                {
                    "level": "info",
                    "message": f"{platform} — {promo}: qualifying spend requirement recorded — verify progress in ad account.",
                }
            )
    return warnings


def platform_comparison(inventory: pd.DataFrame) -> pd.DataFrame:
    if inventory.empty:
        return pd.DataFrame()
    rows = []
    for platform, group in inventory.groupby("Platform"):
        issued = group["Issued Amount"].sum()
        used = group["Used Amount"].sum()
        remaining = group["Remaining Balance"].sum()
        utilization = (used / issued * 100) if issued > 0 else 0
        expiring = group[
            group["Status"].isin({"available", "partially_applied", "reserved"})
        ]["Remaining Balance"].sum()
        rows.append(
            {
                "Platform": platform,
                "Currency": group["Currency"].mode().iloc[0] if len(group) else "",
                "Promotional Value Issued": issued,
                "Utilized": used,
                "Remaining Available": remaining,
                "Utilization %": round(utilization, 1),
                "Expiration Exposure (remaining)": expiring,
            }
        )
    return pd.DataFrame(rows)

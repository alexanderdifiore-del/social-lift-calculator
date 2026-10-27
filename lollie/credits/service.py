"""Credit CRUD, ledger, imports, and reconciliation."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any

import pandas as pd

from lollie.credits.constants import AD_PLATFORMS, IMPORT_FIELD_ALIASES
from lollie.credits.metrics import compute_credit_balances
from lollie.db.connection import get_connection, init_database
from lollie.imports.file_loader import guess_column


class CreditService:
    """SQLite-backed promotional credit operations."""

    def __init__(self) -> None:
        init_database()

    def _duplicate_key(
        self,
        platform: str,
        ad_account_id: str,
        promotion_name: str,
        date_issued: str | None,
        issued_amount: float,
        currency: str,
    ) -> str:
        raw = "|".join(
            [
                platform.strip().lower(),
                ad_account_id.strip().lower(),
                promotion_name.strip().lower(),
                (date_issued or "")[:10],
                f"{issued_amount:.4f}",
                currency.strip().upper(),
            ]
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def list_credits(
        self,
        *,
        include_demo: bool = False,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        clauses = ["1=1"]
        params: list[Any] = []
        if not include_demo:
            clauses.append("pc.is_demo = 0")
        for key, column in [
            ("platform", "pc.platform"),
            ("ad_account_id", "pc.ad_account_id"),
            ("artist", "pc.artist"),
            ("campaign", "pc.campaign"),
            ("market", "pc.market"),
            ("credit_status", "pc.credit_status"),
        ]:
            value = filters.get(key)
            if value and value != "All":
                clauses.append(f"{column} = ?")
                params.append(value)

        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        if date_from:
            clauses.append("(pc.date_issued IS NULL OR pc.date_issued >= ?)")
            params.append(str(date_from))
        if date_to:
            clauses.append("(pc.date_issued IS NULL OR pc.date_issued <= ?)")
            params.append(str(date_to))

        query = f"""
            SELECT pc.*,
                COALESCE(SUM(CASE WHEN cl.entry_type = 'applied' THEN cl.amount ELSE 0 END), 0)
                    AS applied_total,
                COALESCE(SUM(CASE WHEN cl.entry_type = 'reserved' THEN cl.amount ELSE 0 END), 0)
                    AS reserved_total
            FROM promotional_credits pc
            LEFT JOIN credit_ledger cl ON cl.credit_id = pc.id
            WHERE {' AND '.join(clauses)}
            GROUP BY pc.id
            ORDER BY pc.expiration_date IS NULL, pc.expiration_date, pc.platform
        """
        with get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_credit(self, credit_id: int) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM promotional_credits WHERE id = ?",
                (credit_id,),
            ).fetchone()
        return dict(row) if row else None

    def ledger_for_credit(self, credit_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM credit_ledger
                WHERE credit_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (credit_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_credit(
        self,
        payload: dict[str, Any],
        *,
        is_demo: bool = False,
    ) -> int:
        duplicate_key = self._duplicate_key(
            payload["platform"],
            payload["ad_account_id"],
            payload["promotion_name"],
            payload.get("date_issued"),
            float(payload["original_issued_amount"]),
            payload["currency"],
        )
        existing = self.find_duplicate(duplicate_key)
        if existing and not is_demo:
            raise ValueError(
                f"Possible duplicate credit (existing id {existing['id']}). "
                "Adjust identifiers or reconcile the existing record."
            )

        reconciled_sources = {"Platform billing export", "Reconciled billing"}
        manual = payload.get("verification_source", "Manual entry") not in reconciled_sources
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO promotional_credits (
                    platform, ad_account_id, promotion_name, credit_category,
                    application_mode, original_issued_amount, currency,
                    date_issued, activation_date, expiration_date,
                    qualifying_spend_requirement, qualifying_spend_currency,
                    eligibility_restrictions, eligible_campaigns,
                    artist, campaign, market, credit_status,
                    verification_source, last_verified_date, notes,
                    is_demo, is_manual_unreconciled, duplicate_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["platform"],
                    payload["ad_account_id"],
                    payload["promotion_name"],
                    payload["credit_category"],
                    payload.get("application_mode"),
                    float(payload["original_issued_amount"]),
                    payload["currency"].upper(),
                    payload.get("date_issued"),
                    payload.get("activation_date"),
                    payload.get("expiration_date"),
                    payload.get("qualifying_spend_requirement"),
                    payload.get("qualifying_spend_currency"),
                    payload.get("eligibility_restrictions"),
                    payload.get("eligible_campaigns"),
                    payload.get("artist"),
                    payload.get("campaign"),
                    payload.get("market"),
                    payload.get("credit_status", "available"),
                    payload.get("verification_source", "Manual entry"),
                    payload.get("last_verified_date") or date.today().isoformat(),
                    payload.get("notes"),
                    1 if is_demo else 0,
                    1 if manual else 0,
                    duplicate_key,
                ),
            )
            credit_id = int(cursor.lastrowid)
            applied = float(payload.get("amount_applied") or 0)
            if applied > 0:
                conn.execute(
                    """
                    INSERT INTO credit_ledger (
                        credit_id, entry_type, amount, currency,
                        verification_source, reference, is_demo
                    ) VALUES (?, 'applied', ?, ?, ?, ?, ?)
                    """,
                    (
                        credit_id,
                        applied,
                        payload["currency"].upper(),
                        payload.get("verification_source", "Manual entry"),
                        "Initial applied amount on create",
                        1 if is_demo else 0,
                    ),
                )
            conn.commit()
        return credit_id

    def find_duplicate(self, duplicate_key: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM promotional_credits WHERE duplicate_key = ? AND is_demo = 0 LIMIT 1",
                (duplicate_key,),
            ).fetchone()
        return dict(row) if row else None

    def add_ledger_entry(
        self,
        credit_id: int,
        entry_type: str,
        amount: float,
        *,
        currency: str | None = None,
        campaign: str | None = None,
        reference: str | None = None,
        verification_source: str = "Manual entry",
    ) -> None:
        allowed = {"applied", "reserved", "release_reserve", "adjustment", "expire", "import_reconcile"}
        if entry_type not in allowed:
            raise ValueError(f"Unsupported ledger entry type: {entry_type}")

        credit = self.get_credit(credit_id)
        if not credit:
            raise ValueError("Credit not found.")
        currency = (currency or credit["currency"]).upper()

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO credit_ledger (
                    credit_id, entry_type, amount, currency, campaign,
                    reference, verification_source, is_demo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    credit_id,
                    entry_type,
                    float(amount),
                    currency,
                    campaign,
                    reference,
                    verification_source,
                    credit["is_demo"],
                ),
            )
            if entry_type == "import_reconcile":
                conn.execute(
                    """
                    UPDATE promotional_credits
                    SET is_manual_unreconciled = 0,
                        last_verified_date = ?,
                        verification_source = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (date.today().isoformat(), verification_source, credit_id),
                )
            conn.commit()

    def add_allocation(
        self,
        credit_id: int,
        campaign_name: str,
        allocation_type: str,
        *,
        campaign_id: str | None = None,
        amount: float | None = None,
        notes: str | None = None,
    ) -> None:
        if allocation_type not in {"eligible", "planned", "applied"}:
            raise ValueError("allocation_type must be eligible, planned, or applied")
        credit = self.get_credit(credit_id)
        if not credit:
            raise ValueError("Credit not found.")
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO credit_allocations (
                    credit_id, campaign_name, campaign_id, allocation_type,
                    amount, currency, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    credit_id,
                    campaign_name,
                    campaign_id,
                    allocation_type,
                    amount,
                    credit["currency"],
                    notes,
                ),
            )
            if allocation_type == "planned" and amount:
                conn.execute(
                    """
                    INSERT INTO credit_ledger (
                        credit_id, entry_type, amount, currency, campaign,
                        reference, verification_source, is_demo
                    ) VALUES (?, 'reserved', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        credit_id,
                        amount,
                        credit["currency"],
                        campaign_name,
                        "Planned campaign allocation",
                        "Manual entry",
                        credit["is_demo"],
                    ),
                )
            if allocation_type == "applied" and amount:
                conn.execute(
                    """
                    INSERT INTO credit_ledger (
                        credit_id, entry_type, amount, currency, campaign,
                        reference, verification_source, is_demo
                    ) VALUES (?, 'applied', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        credit_id,
                        amount,
                        credit["currency"],
                        campaign_name,
                        "Applied on campaign (verified entry)",
                        credit.get("verification_source", "Manual entry"),
                        credit["is_demo"],
                    ),
                )
            conn.commit()

    def list_allocations(self, credit_id: int | None = None) -> list[dict[str, Any]]:
        with get_connection() as conn:
            if credit_id:
                rows = conn.execute(
                    "SELECT * FROM credit_allocations WHERE credit_id = ? ORDER BY id DESC",
                    (credit_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM credit_allocations ORDER BY id DESC"
                ).fetchall()
        return [dict(row) for row in rows]

    def record_campaign_spend(self, payload: dict[str, Any], *, is_demo: bool = False) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO campaign_spend (
                    platform, ad_account_id, artist, campaign_name, campaign_id,
                    market, gross_media_spend, currency, spend_start, spend_end,
                    verification_source, is_demo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["platform"],
                    payload.get("ad_account_id"),
                    payload.get("artist"),
                    payload["campaign_name"],
                    payload.get("campaign_id"),
                    payload.get("market"),
                    float(payload["gross_media_spend"]),
                    payload["currency"].upper(),
                    payload.get("spend_start"),
                    payload.get("spend_end"),
                    payload.get("verification_source", "Manual entry"),
                    1 if is_demo else 0,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def campaign_cost_summary(
        self,
        *,
        include_demo: bool = False,
    ) -> pd.DataFrame:
        demo_clause = "" if include_demo else "AND cs.is_demo = 0"
        query = f"""
            SELECT cs.*,
                COALESCE(
                    (
                        SELECT SUM(cl.amount)
                        FROM credit_ledger cl
                        JOIN promotional_credits pc ON pc.id = cl.credit_id
                        WHERE cl.entry_type = 'applied'
                          AND cl.campaign = cs.campaign_name
                          AND pc.platform = cs.platform
                          AND cl.verification_source IN (
                              'Platform billing export', 'Reconciled billing'
                          )
                    ), 0
                ) AS verified_applied_from_billing,
                COALESCE(
                    (
                        SELECT SUM(cl.amount)
                        FROM credit_ledger cl
                        JOIN promotional_credits pc ON pc.id = cl.credit_id
                        WHERE cl.entry_type = 'applied'
                          AND cl.campaign = cs.campaign_name
                          AND pc.platform = cs.platform
                    ), 0
                ) AS total_applied_all_sources
            FROM campaign_spend cs
            WHERE 1=1 {demo_clause}
            ORDER BY cs.created_at DESC
        """
        with get_connection() as conn:
            rows = conn.execute(query).fetchall()
        records = []
        for row in rows:
            gross = float(row["gross_media_spend"])
            verified = float(row["verified_applied_from_billing"])
            records.append(
                {
                    "Platform": row["platform"],
                    "Campaign": row["campaign_name"],
                    "Artist": row.get("artist") or "",
                    "Gross Media Spend": gross,
                    "Verified Promotional Credits Applied": verified,
                    "Net Media Cost (verified credits only)": max(gross - verified, 0),
                    "Currency": row["currency"],
                    "All Applied Credits (incl. manual)": float(row["total_applied_all_sources"]),
                }
            )
        return pd.DataFrame(records)

    def import_rows(
        self,
        dataframe: pd.DataFrame,
        column_map: dict[str, str | None],
        *,
        file_type: str,
        filename: str | None = None,
        is_demo: bool = False,
    ) -> tuple[int, list[str]]:
        errors: list[str] = []
        imported = 0
        with get_connection() as conn:
            batch = conn.execute(
                """
                INSERT INTO import_batches (filename, file_type, row_count, notes)
                VALUES (?, ?, ?, ?)
                """,
                (filename, file_type, len(dataframe), "Promotional credit import"),
            )
            batch_id = batch.lastrowid

        for idx, row in dataframe.iterrows():
            try:
                payload = self._row_to_payload(row, column_map)
                if not payload.get("platform") or payload["platform"] not in AD_PLATFORMS:
                    errors.append(f"Row {idx}: unsupported or missing platform.")
                    continue
                payload["verification_source"] = payload.get("verification_source") or (
                    "CSV import" if file_type == "csv" else "Excel import"
                )
                if float(payload.get("amount_applied") or 0) == 0:
                    payload.pop("amount_applied", None)
                self.create_credit(payload, is_demo=is_demo)
                imported += 1
            except ValueError as exc:
                errors.append(f"Row {idx}: {exc}")
            except Exception as exc:
                errors.append(f"Row {idx}: {exc}")

        with get_connection() as conn:
            conn.execute(
                "UPDATE import_batches SET row_count = ? WHERE id = ?",
                (imported, batch_id),
            )
            conn.commit()
        return imported, errors

    def _row_to_payload(
        self,
        row: pd.Series,
        column_map: dict[str, str | None],
    ) -> dict[str, Any]:
        def val(field: str) -> Any:
            col = column_map.get(field)
            if not col or col not in row.index:
                return None
            value = row[col]
            if pd.isna(value):
                return None
            return value

        issued = val("issued_amount")
        if issued is None:
            raise ValueError("issued amount is required.")
        return {
            "platform": str(val("platform")).strip(),
            "ad_account_id": str(val("ad_account_id") or "UNKNOWN").strip(),
            "promotion_name": str(val("promotion_name") or "Imported promotion").strip(),
            "credit_category": str(val("credit_category") or "Other / custom").strip(),
            "original_issued_amount": float(issued),
            "currency": str(val("currency") or "USD").strip().upper(),
            "date_issued": self._normalize_date(val("date_issued")),
            "activation_date": self._normalize_date(val("activation_date")),
            "expiration_date": self._normalize_date(val("expiration_date")),
            "qualifying_spend_requirement": (
                float(val("qualifying_spend_requirement"))
                if val("qualifying_spend_requirement") not in (None, "")
                else None
            ),
            "amount_applied": (
                float(val("amount_applied"))
                if val("amount_applied") not in (None, "")
                else 0
            ),
            "verification_source": (
                str(val("verification_source")).strip()
                if val("verification_source") is not None
                else None
            ),
            "artist": str(val("artist")).strip() if val("artist") is not None else None,
            "campaign": str(val("campaign")).strip() if val("campaign") is not None else None,
            "market": str(val("market")).strip() if val("market") is not None else None,
            "notes": str(val("notes")).strip() if val("notes") is not None else None,
            "credit_status": "available",
        }

    @staticmethod
    def _normalize_date(value: Any) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, (datetime, date)):
            return value.isoformat()[:10]
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return str(value)[:10]
        return parsed.date().isoformat()

    def suggest_column_map(self, columns: list[str]) -> dict[str, str | None]:
        mapping: dict[str, str | None] = {}
        for field, aliases in IMPORT_FIELD_ALIASES.items():
            mapping[field] = guess_column(columns, aliases)
        return mapping

    def load_demo_records(self) -> int:
        """Load synthetic demo credits (explicit opt-in only)."""
        from lollie.credits.demo_data import DEMO_CREDITS, DEMO_SPEND

        self.clear_demo_records()
        count = 0
        for payload in DEMO_CREDITS:
            self.create_credit(payload, is_demo=True)
            count += 1
        for spend in DEMO_SPEND:
            self.record_campaign_spend(spend, is_demo=True)
        return count

    def clear_demo_records(self) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM credit_ledger WHERE is_demo = 1")
            conn.execute("DELETE FROM credit_allocations WHERE credit_id IN (SELECT id FROM promotional_credits WHERE is_demo = 1)")
            conn.execute("DELETE FROM promotional_credits WHERE is_demo = 1")
            conn.execute("DELETE FROM campaign_spend WHERE is_demo = 1")
            conn.commit()

    def discrepancy_flags(self, include_demo: bool = False) -> list[str]:
        flags: list[str] = []
        credits = self.list_credits(include_demo=include_demo)
        for credit in credits:
            balances = compute_credit_balances(credit)
            if balances["applied"] > balances["issued"] + 0.01:
                flags.append(
                    f"Credit #{credit['id']} ({credit['promotion_name']}): applied exceeds issued."
                )
            if credit.get("is_manual_unreconciled") and balances["applied"] > 0:
                flags.append(
                    f"Credit #{credit['id']} ({credit['promotion_name']}): manual record shows utilization — reconcile with billing."
                )
        return flags

    def register_exchange_rate(
        self,
        rate_date: str,
        from_currency: str,
        to_currency: str,
        rate: float,
        source: str,
    ) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO exchange_rates (rate_date, from_currency, to_currency, rate, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                (rate_date, from_currency.upper(), to_currency.upper(), float(rate), source),
            )
            conn.commit()

    def convert_amount(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        rate_date: str,
    ) -> float | None:
        if from_currency.upper() == to_currency.upper():
            return amount
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT rate FROM exchange_rates
                WHERE rate_date = ? AND from_currency = ? AND to_currency = ?
                ORDER BY id DESC LIMIT 1
                """,
                (rate_date, from_currency.upper(), to_currency.upper()),
            ).fetchone()
        if not row:
            return None
        return amount * float(row["rate"])

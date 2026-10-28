import os
from datetime import date, timedelta

import pytest

from lollie.credits.metrics import build_inventory_dataframe, expiration_warnings
from lollie.credits.service import CreditService
from lollie.credits.settings import WarningSettings
from lollie.db.connection import get_db_path, init_database


@pytest.fixture()
def credit_service(tmp_path, monkeypatch):
    db_path = tmp_path / "test_credits.db"
    monkeypatch.setenv("LOLLIE_DB_PATH", str(db_path))
    init_database()
    return CreditService()


def test_create_credit_and_ledger_balance(credit_service: CreditService):
    credit_id = credit_service.create_credit(
        {
            "platform": "Meta Ads",
            "ad_account_id": "act_123",
            "promotion_name": "Test Promo",
            "credit_category": "Account-level promotional credit",
            "original_issued_amount": 1000,
            "currency": "USD",
            "credit_status": "available",
            "verification_source": "Manual entry",
            "amount_applied": 250,
        }
    )
    rows = credit_service.list_credits()
    assert len(rows) == 1
    assert rows[0]["id"] == credit_id
    assert rows[0]["applied_total"] == 250
    assert rows[0]["is_manual_unreconciled"] == 1


def test_duplicate_detection(credit_service: CreditService):
    payload = {
        "platform": "TikTok Ads",
        "ad_account_id": "tt_1",
        "promotion_name": "Dup Test",
        "credit_category": "Free promotional credit",
        "original_issued_amount": 500,
        "currency": "USD",
        "date_issued": "2026-01-01",
        "credit_status": "available",
        "verification_source": "Manual entry",
    }
    credit_service.create_credit(payload)
    with pytest.raises(ValueError, match="duplicate"):
        credit_service.create_credit(payload)


def test_planned_allocation_does_not_affect_applied_total(credit_service: CreditService):
    credit_id = credit_service.create_credit(
        {
            "platform": "Snapchat Ads",
            "ad_account_id": "sc_9",
            "promotion_name": "Snap Promo",
            "credit_category": "Conditional promotional credit",
            "original_issued_amount": 800,
            "currency": "USD",
            "credit_status": "available",
            "verification_source": "Manual entry",
        }
    )
    credit_service.add_allocation(credit_id, "Launch Campaign", "planned", amount=200)
    row = credit_service.list_credits()[0]
    assert row["reserved_total"] == 200
    assert row["applied_total"] == 0


def test_expiration_warning_thresholds(credit_service: CreditService):
    soon = (date.today() + timedelta(days=5)).isoformat()
    credit_service.create_credit(
        {
            "platform": "Google Ads / YouTube",
            "ad_account_id": "g_1",
            "promotion_name": "Expiring",
            "credit_category": "Issued promotional credit (available)",
            "original_issued_amount": 100,
            "currency": "USD",
            "expiration_date": soon,
            "credit_status": "available",
            "verification_source": "Manual entry",
        }
    )
    rows = credit_service.list_credits()
    warnings = expiration_warnings(rows, WarningSettings())
    assert any("expires in" in w["message"] for w in warnings)


def test_import_mapping_and_row_import(credit_service: CreditService):
    import pandas as pd

    frame = pd.DataFrame(
        [
            {
                "platform": "Meta Ads",
                "account_id": "act_999",
                "promo_name": "Import Promo",
                "amount": 1200,
                "currency_code": "USD",
            }
        ]
    )
    mapping = credit_service.suggest_column_map(list(frame.columns))
    mapping["promotion_name"] = "promo_name"
    mapping["ad_account_id"] = "account_id"
    mapping["issued_amount"] = "amount"
    mapping["currency"] = "currency_code"
    imported, errors = credit_service.import_rows(
        frame, mapping, file_type="csv", filename="test.csv"
    )
    assert imported == 1
    assert not errors
    inventory = build_inventory_dataframe(credit_service.list_credits())
    assert inventory.iloc[0]["Issued Amount"] == 1200


def test_demo_mode_isolated(tmp_path, monkeypatch):
    db_path = tmp_path / "demo.db"
    monkeypatch.setenv("LOLLIE_DB_PATH", str(db_path))
    service = CreditService()
    service.create_credit(
        {
            "platform": "Meta Ads",
            "ad_account_id": "real",
            "promotion_name": "Real Credit",
            "credit_category": "Account-level promotional credit",
            "original_issued_amount": 100,
            "currency": "USD",
            "credit_status": "available",
            "verification_source": "Manual entry",
        }
    )
    service.load_demo_records()
    assert len(service.list_credits(include_demo=False)) == 1
    assert len(service.list_credits(include_demo=True)) == 5

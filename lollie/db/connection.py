"""SQLite connection helpers."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1


def get_db_path() -> Path:
    override = os.environ.get("LOLLIE_DB_PATH")
    if override:
        return Path(override)
    root = Path(__file__).resolve().parents[2]
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "lollie_credits.db"


def get_connection() -> sqlite3.Connection:
    path = get_db_path()
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_database() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS exchange_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rate_date TEXT NOT NULL,
                from_currency TEXT NOT NULL,
                to_currency TEXT NOT NULL,
                rate REAL NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS import_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                file_type TEXT,
                row_count INTEGER,
                imported_at TEXT NOT NULL DEFAULT (datetime('now')),
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS promotional_credits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                ad_account_id TEXT NOT NULL,
                promotion_name TEXT NOT NULL,
                credit_category TEXT NOT NULL,
                application_mode TEXT,
                original_issued_amount REAL NOT NULL,
                currency TEXT NOT NULL,
                date_issued TEXT,
                activation_date TEXT,
                expiration_date TEXT,
                qualifying_spend_requirement REAL,
                qualifying_spend_currency TEXT,
                eligibility_restrictions TEXT,
                eligible_campaigns TEXT,
                artist TEXT,
                campaign TEXT,
                market TEXT,
                credit_status TEXT NOT NULL,
                verification_source TEXT NOT NULL,
                last_verified_date TEXT,
                notes TEXT,
                is_demo INTEGER NOT NULL DEFAULT 0,
                is_manual_unreconciled INTEGER NOT NULL DEFAULT 1,
                duplicate_key TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS credit_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                credit_id INTEGER NOT NULL,
                entry_type TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                campaign TEXT,
                reference TEXT,
                verification_source TEXT,
                is_demo INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (credit_id) REFERENCES promotional_credits(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS credit_allocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                credit_id INTEGER NOT NULL,
                campaign_name TEXT NOT NULL,
                campaign_id TEXT,
                allocation_type TEXT NOT NULL,
                amount REAL,
                currency TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (credit_id) REFERENCES promotional_credits(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS campaign_spend (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                ad_account_id TEXT,
                artist TEXT,
                campaign_name TEXT NOT NULL,
                campaign_id TEXT,
                market TEXT,
                gross_media_spend REAL NOT NULL,
                currency TEXT NOT NULL,
                spend_start TEXT,
                spend_end TEXT,
                verification_source TEXT NOT NULL DEFAULT 'Manual entry',
                is_demo INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_credits_platform ON promotional_credits(platform);
            CREATE INDEX IF NOT EXISTS idx_credits_status ON promotional_credits(credit_status);
            CREATE INDEX IF NOT EXISTS idx_credits_expiration ON promotional_credits(expiration_date);
            CREATE INDEX IF NOT EXISTS idx_ledger_credit ON credit_ledger(credit_id);
            CREATE INDEX IF NOT EXISTS idx_credits_duplicate ON promotional_credits(duplicate_key);
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        conn.commit()

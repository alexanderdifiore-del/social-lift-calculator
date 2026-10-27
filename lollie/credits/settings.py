"""Configurable warning thresholds for credit monitoring."""

from __future__ import annotations

from dataclasses import dataclass

from lollie.db.connection import get_connection


@dataclass
class WarningSettings:
    expiring_soon_days: int = 7
    expiring_warning_days: int = 30


DEFAULT_SETTINGS = WarningSettings()


def load_warning_settings() -> WarningSettings:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT key, value FROM app_settings WHERE key LIKE 'warn_%'"
        ).fetchall()
    values = {row["key"]: row["value"] for row in rows}
    return WarningSettings(
        expiring_soon_days=int(values.get("warn_expiring_soon_days", 7)),
        expiring_warning_days=int(values.get("warn_expiring_warning_days", 30)),
    )


def save_warning_settings(settings: WarningSettings) -> None:
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            [
                ("warn_expiring_soon_days", str(settings.expiring_soon_days)),
                ("warn_expiring_warning_days", str(settings.expiring_warning_days)),
            ],
        )
        conn.commit()

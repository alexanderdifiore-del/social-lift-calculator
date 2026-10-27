"""Flexible CSV/Excel loading (patterns aligned with the classic lift calculator)."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd


def normalize_column_names(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Strip BOM/noise and drop unnamed empty columns."""
    frame = dataframe.copy()
    frame.columns = [
        str(col)
        .strip()
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("\ufeff", "")
        for col in frame.columns
    ]
    keep = [not str(col).lower().startswith("unnamed") for col in frame.columns]
    return frame.loc[:, keep]


def _decode_bytes(raw_bytes: bytes) -> str | None:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except Exception:
            continue
    return None


def _read_csv_text(text: str) -> pd.DataFrame:
    lines = [line for line in text.splitlines() if line.strip()]
    header_line_index = 0
    for i, line in enumerate(lines[:30]):
        normalized = line.lower().replace(" ", "_")
        if any(token in normalized for token in ("platform", "account", "credit", "amount", "currency")):
            header_line_index = i
            break
    cleaned = "\n".join(lines[header_line_index:])
    for separator in (",", "\t", ";"):
        try:
            candidate = pd.read_csv(io.StringIO(cleaned), sep=separator)
            candidate = candidate.dropna(axis=1, how="all")
            if len(candidate.columns) >= 2:
                return candidate
        except Exception:
            pass
    return pd.read_csv(io.StringIO(cleaned), sep=None, engine="python")


def load_tabular_upload(
    uploaded_file: Any,
    *,
    sheet_name: str | int | None = 0,
) -> pd.DataFrame:
    """
    Load an uploaded CSV or Excel file into a dataframe.

    ``uploaded_file`` is a Streamlit UploadedFile or any file-like object with
    ``getvalue()``, ``read()``, or ``name``.
    """
    name = getattr(uploaded_file, "name", "") or ""
    lower = name.lower()
    if hasattr(uploaded_file, "getvalue"):
        raw = uploaded_file.getvalue()
    else:
        raw = uploaded_file.read()

    if lower.endswith((".xlsx", ".xlsm", ".xls")):
        buffer = io.BytesIO(raw)
        frame = pd.read_excel(buffer, sheet_name=sheet_name or 0)
    else:
        text = _decode_bytes(raw)
        if text is None:
            raise ValueError("Could not decode uploaded file.")
        frame = _read_csv_text(text)

    return normalize_column_names(frame.dropna(axis=1, how="all"))


def guess_column(columns: list[str], keywords: list[str]) -> str | None:
    for keyword in keywords:
        for col in columns:
            normalized = col.lower().replace(" ", "_")
            if keyword in normalized:
                return col
    return None

"""Flexible CSV/Excel loading for Lollie uploads.

Handles BOMs, odd encodings, comma/tab/semicolon separators, and the title rows
that Numbers, Google Ads and other tools put above the real header row.
"""

from __future__ import annotations

import io
from typing import Any, Iterable

import pandas as pd

DEFAULT_HEADER_HINTS = ("platform", "account", "credit", "amount", "currency")
EXCEL_SUFFIXES = (".xlsx", ".xlsm", ".xls")


def normalize_column_names(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Strip BOM/noise and drop unnamed empty columns."""
    frame = dataframe.copy()
    frame.columns = [
        str(col).strip().replace("\n", " ").replace("\r", " ").replace("\ufeff", "")
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


def _looks_like_header(cells: Iterable[object], hints: tuple[str, ...]) -> bool:
    """A real header row names several expected fields; a title row names at most one."""
    present = [str(c).lower().replace(" ", "_") for c in cells if pd.notna(c)]
    text = " ".join(present)
    needed = min(2, len(hints))
    return sum(hint in text for hint in hints) >= needed


def _read_csv_text(text: str, hints: tuple[str, ...]) -> pd.DataFrame:
    lines = [line for line in text.splitlines() if line.strip()]
    header_index = 0
    for i, line in enumerate(lines[:30]):
        has_separator = any(sep in line for sep in (",", "\t", ";"))
        if has_separator and _looks_like_header([line], hints):
            header_index = i
            break
    cleaned = "\n".join(lines[header_index:])
    for separator in (",", "\t", ";"):
        try:
            candidate = pd.read_csv(io.StringIO(cleaned), sep=separator)
            candidate = candidate.dropna(axis=1, how="all")
            if len(candidate.columns) >= 2:
                return candidate
        except Exception:
            pass
    return pd.read_csv(io.StringIO(cleaned), sep=None, engine="python")


def _read_excel(raw: bytes, hints: tuple[str, ...], sheet_name: str | int) -> pd.DataFrame:
    probe = pd.read_excel(io.BytesIO(raw), sheet_name=sheet_name, header=None)
    header_index = 0
    for i in range(min(len(probe), 30)):
        if _looks_like_header(probe.iloc[i].tolist(), hints):
            header_index = i
            break
    return pd.read_excel(io.BytesIO(raw), sheet_name=sheet_name, header=header_index)


def read_raw_bytes(uploaded_file: Any) -> bytes:
    if hasattr(uploaded_file, "getvalue"):
        return uploaded_file.getvalue()
    return uploaded_file.read()


def load_tabular_upload(
    uploaded_file: Any,
    *,
    header_hints: tuple[str, ...] = DEFAULT_HEADER_HINTS,
    sheet_name: str | int = 0,
) -> pd.DataFrame:
    """Load an uploaded CSV or Excel file.

    ``header_hints`` are substrings used to find the real header row below any
    title lines. ``uploaded_file`` is a Streamlit UploadedFile or any object
    with ``name`` and ``getvalue()``/``read()``.
    """
    name = (getattr(uploaded_file, "name", "") or "").lower()
    raw = read_raw_bytes(uploaded_file)

    if name.endswith(EXCEL_SUFFIXES):
        frame = _read_excel(raw, header_hints, sheet_name)
    else:
        text = _decode_bytes(raw)
        if text is None:
            raise ValueError("The uploaded file could not be decoded. Please export it again as a CSV.")
        frame = _read_csv_text(text, header_hints)

    return normalize_column_names(frame.dropna(axis=1, how="all"))


def guess_column(columns: list[str], keywords: list[str]) -> str | None:
    for keyword in keywords:
        for col in columns:
            if keyword in col.lower().replace(" ", "_"):
                return col
    return None

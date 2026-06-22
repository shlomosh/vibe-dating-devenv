from __future__ import annotations

import csv
from pathlib import Path

from lib.config import REQUIRED_CSV_COLUMNS, SUPPORTED_SOURCES


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Seed CSV not found: {path}")
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"Seed CSV has no header: {path}")
        for col in REQUIRED_CSV_COLUMNS:
            if col not in reader.fieldnames:
                raise ValueError(f"Seed CSV missing column {col!r}: {path}")
        rows = []
        for row in reader:
            rows.append({k: (v or "").strip() for k, v in row.items()})
        return rows


def validate_csv_sources(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    bad = {r.get("source", "").lower() for r in rows} - SUPPORTED_SOURCES
    bad.discard("")
    if bad:
        errors.append(f"Unsupported source values in seed CSV: {bad}")
    return errors

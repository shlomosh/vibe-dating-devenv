from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from lib.config import REQUIRED_CSV_COLUMNS
from lib.durable_write import write_text_durable
from lib.log import log
from lib.resource.base import ResourceBackend, ResourceRow


def _is_available(val) -> bool:
    if val is None:
        return True
    try:
        if pd.isna(val):
            return True
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    return s == "" or s == "<NA>"


class CsvfileBackend(ResourceBackend):
    def __init__(self, path: Path):
        self._path = path.resolve()
        self._df: pd.DataFrame | None = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def store_label(self) -> str:
        return str(self._path)

    def reload(self) -> None:
        if not self._path.exists():
            raise FileNotFoundError(f"Resource CSV not found: {self._path}")
        log.info("csv: reading %s", self._path)
        self._df = pd.read_csv(self._path, dtype={"date": "string"}, keep_default_na=True)
        log.info("csv: read %d rows", len(self._df))

    def validate_schema(self) -> list[str]:
        errors: list[str] = []
        if self._df is None:
            self.reload()
        assert self._df is not None
        for col in REQUIRED_CSV_COLUMNS:
            if col not in self._df.columns:
                errors.append(f"Missing required column: {col}")
        return errors

    def classes_in_store(self) -> set[str]:
        if self._df is None:
            self.reload()
        assert self._df is not None
        if "class" not in self._df.columns:
            return set()
        return set(self._df["class"].astype(str).unique())

    def select_next(self, class_name: str) -> ResourceRow | None:
        if self._df is None:
            self.reload()
        assert self._df is not None
        df = self._df
        mask = df["class"].astype(str) == class_name
        mask &= df["date"].apply(_is_available)
        subset = df[mask]
        if subset.empty:
            return None
        idx = subset.index[0]
        row = df.loc[idx]
        return ResourceRow(
            index=int(idx),
            url=str(row["url"]).strip(),
            source=str(row["source"]).strip(),
            class_name=str(row["class"]).strip(),
            raw=row.to_dict(),
        )

    def mark_used(self, row: ResourceRow) -> None:
        if self._df is None:
            raise RuntimeError("Resource backend not loaded")
        stamp = datetime.now().isoformat(timespec="seconds")
        self._df.loc[row.index, "date"] = stamp
        self._save()

    def _save(self) -> None:
        assert self._df is not None
        log.info("csv: writing %s", self._path)
        write_text_durable(self._path, self._df.to_csv(index=False))
        log.info("csv: wrote %s", self._path)

    def counts(self) -> dict[str, dict[str, int]]:
        if self._df is None:
            self.reload()
        assert self._df is not None
        result: dict[str, dict[str, int]] = {}
        for class_name, group in self._df.groupby(self._df["class"].astype(str)):
            pending = int(group["date"].apply(_is_available).sum())
            used = len(group) - pending
            result[class_name] = {"pending": pending, "used": used}
        return result

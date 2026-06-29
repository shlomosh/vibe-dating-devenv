from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ResourceRow:
    index: int
    url: str
    source: str
    class_name: str
    raw: dict[str, Any]


class ResourceBackend(ABC):
    @property
    def store_label(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def reload(self) -> None:
        ...

    @abstractmethod
    def select_next(self, class_name: str) -> ResourceRow | None:
        ...

    @abstractmethod
    def mark_used(self, row: ResourceRow) -> None:
        ...

    @abstractmethod
    def mark_bad(self, row: ResourceRow) -> None:
        """Flag a row whose media can't be downloaded so it is never retried."""

    @abstractmethod
    def counts(self) -> dict[str, dict[str, int]]:
        ...

    @abstractmethod
    def validate_schema(self) -> list[str]:
        """Return list of errors (empty if ok)."""

    @abstractmethod
    def classes_in_store(self) -> set[str]:
        ...

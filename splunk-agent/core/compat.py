"""Small compatibility helpers (keeps the code base runnable on 3.10+ while targeting 3.12)."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """Equivalent of ``enum.StrEnum`` (3.11+): members behave as plain strings."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)

    def __format__(self, spec: str) -> str:  # pragma: no cover - trivial
        return format(str(self.value), spec)

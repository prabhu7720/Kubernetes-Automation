"""Collector plugin contract.

A collector pulls one kind of metadata from Splunk and writes it to the catalog.
Subclass :class:`Collector` in any module under ``discovery/`` (or a directory in
``plugins.collector_dirs``) and it is picked up automatically.  ``priority``
controls ordering (datasets must exist before field profiling, for example).
"""

from __future__ import annotations

import inspect
import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from catalog.metadata_store import MetadataStore
from core.config import DiscoverySettings
from core.splunk_client import SplunkClientProtocol

log = logging.getLogger(__name__)


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class Collector(ABC):
    name: ClassVar[str] = ""
    priority: ClassVar[int] = 100
    description: ClassVar[str] = ""
    _registry: ClassVar[dict[str, type["Collector"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls.__dict__.get("name") and not inspect.isabstract(cls):
            Collector._registry[cls.name] = cls

    def __init__(self, client: SplunkClientProtocol, store: MetadataStore, settings: DiscoverySettings) -> None:
        self.client = client
        self.store = store
        self.settings = settings
        self.log = logging.getLogger(f"discovery.{self.name}")

    @property
    def index_filter(self) -> str:
        return "index=* OR index=_*" if self.settings.include_internal_indexes else "index=*"

    @abstractmethod
    def run(self) -> int:
        """Collect + store; return number of items stored."""

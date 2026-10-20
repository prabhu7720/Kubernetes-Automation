"""Catalog record types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

METRICS_SOURCETYPE = "__metrics__"


@dataclass(frozen=True)
class IndexInfo:
    name: str
    datatype: str = "event"
    event_count: int = 0
    size_mb: float = 0.0
    earliest: str | None = None
    latest: str | None = None
    disabled: bool = False


@dataclass(frozen=True)
class DatasetInfo:
    index: str
    sourcetype: str
    event_count: int = 0
    last_seen: float | None = None


@dataclass(frozen=True)
class FieldInfo:
    index: str
    sourcetype: str
    name: str
    coverage: float = 0.0
    distinct_count: int = 0
    sample_values: tuple[str, ...] = ()
    is_numeric: bool = False
    kind: str = "field"  # field | metric | dimension


@dataclass(frozen=True)
class DataModelInfo:
    name: str
    app: str | None = None
    accelerated: bool = False
    objects: tuple[str, ...] = ()


@dataclass(frozen=True)
class KnowledgeObject:
    kind: str  # report | alert | saved_search | dashboard | kvstore | lookup_definition | lookup_file
    name: str
    app: str | None = None
    owner: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EntityInfo:
    kind: str  # host | source
    name: str
    event_count: int = 0
    last_seen: float | None = None


def to_dict(obj: Any) -> dict[str, Any]:
    d = asdict(obj)
    for k, v in d.items():
        if isinstance(v, tuple):
            d[k] = list(v)
    return d

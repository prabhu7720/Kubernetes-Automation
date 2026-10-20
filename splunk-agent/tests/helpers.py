"""Shared test fixtures (works with both unittest and pytest)."""

from __future__ import annotations

import functools
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from catalog.metadata_store import MetadataStore  # noqa: E402
from core.config import load_settings  # noqa: E402

SAMPLE_CATALOG = ROOT / "catalog" / "sample_catalog.json"


def make_settings(**overrides: Any):
    base = {"catalog": {"path": ":memory:"}, "logging": {"file": ""}}
    for k, v in overrides.items():
        base.setdefault(k, {}).update(v) if isinstance(v, dict) else base.__setitem__(k, v)
    return load_settings(overrides=base, use_env=False)


def sample_store() -> MetadataStore:
    store = MetadataStore(":memory:")
    store.import_json(SAMPLE_CATALOG)
    return store


@functools.lru_cache(maxsize=1)
def shared_agent():
    from agent import SplunkAgent

    return SplunkAgent(make_settings(), store=sample_store())


def empty_agent():
    from agent import SplunkAgent

    return SplunkAgent(make_settings(), store=MetadataStore(":memory:"))


class FakeSplunkClient:
    """Canned responses keyed by REST path / SPL substring."""

    def __init__(self, rest: dict[str, list[dict]] | None = None, searches: dict[str, list[dict]] | None = None,
                 fail: set[str] | None = None) -> None:
        self.rest = rest or {}
        self.searches = searches or {}
        self.fail = fail or set()
        self.calls: list[str] = []

    def rest_get(self, path: str, **params: Any) -> list[dict]:
        self.calls.append(path)
        if path in self.fail:
            raise RuntimeError(f"boom {path}")
        return self.rest.get(path, [])

    def search(self, spl: str, *, earliest=None, latest=None, max_results=10000) -> list[dict]:
        self.calls.append(spl)
        for key, rows in self.searches.items():
            if key in spl:
                return rows
        return []

    def server_info(self) -> dict:
        return {"serverName": "fake", "version": "9.3.0"}


def fieldsummary(*names: str, count: int = 100) -> list[dict]:
    return [{"field": n, "count": count, "distinct_count": 5, "numeric_count": 0,
             "values": json.dumps([{"value": "x", "count": 1}])} for n in names]

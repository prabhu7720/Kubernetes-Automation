"""Runs discovery collectors in priority order with per-collector fault isolation."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Iterable

from catalog.metadata_store import MetadataStore
from core.config import DiscoverySettings
from core.exceptions import DiscoveryError
from core.plugins import load_plugins
from core.splunk_client import SplunkClientProtocol
from discovery.base import Collector

log = logging.getLogger(__name__)


@dataclass
class CollectorResult:
    name: str
    ok: bool
    count: int = 0
    seconds: float = 0.0
    error: str | None = None


@dataclass
class DiscoveryReport:
    results: list[CollectorResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "started_at": self.started_at, "results": [asdict(r) for r in self.results]}


class DiscoveryEngine:
    def __init__(self, client: SplunkClientProtocol, store: MetadataStore, settings: DiscoverySettings,
                 extra_dirs: Iterable[str] = ()) -> None:
        self.client = client
        self.store = store
        self.settings = settings
        load_plugins("discovery", extra_dirs, skip=("base", "engine"))

    @staticmethod
    def available() -> list[type[Collector]]:
        return sorted(Collector._registry.values(), key=lambda c: (c.priority, c.name))

    def run(self, only: Iterable[str] | None = None) -> DiscoveryReport:
        wanted = set(only or self.settings.collectors or [])
        unknown = wanted - {c.name for c in self.available()}
        if unknown:
            raise DiscoveryError(f"Unknown collector(s): {', '.join(sorted(unknown))}")
        report = DiscoveryReport()
        for cls in self.available():
            if wanted and cls.name not in wanted:
                continue
            start = time.monotonic()
            try:
                count = cls(self.client, self.store, self.settings).run()
                report.results.append(CollectorResult(cls.name, True, count, round(time.monotonic() - start, 2)))
                log.info("discovery %-15s %6d item(s) in %.2fs", cls.name, count, time.monotonic() - start)
            except Exception as exc:  # noqa: BLE001 - isolate collector failures
                report.results.append(CollectorResult(cls.name, False, 0, round(time.monotonic() - start, 2), str(exc)))
                log.error("discovery %s failed: %s", cls.name, exc)
        try:
            self.store.set_meta("server_info", self.client.server_info())
        except Exception as exc:  # noqa: BLE001
            log.debug("server_info unavailable: %s", exc)
        self.store.set_meta("last_discovery", {"at": time.time(), "ok": report.ok,
                                               "results": [asdict(r) for r in report.results]})
        return report

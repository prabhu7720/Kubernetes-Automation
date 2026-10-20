"""Index inventory (event + metric indexes) via REST ``data/indexes``."""

from __future__ import annotations

from catalog.models import IndexInfo
from discovery.base import Collector, to_bool, to_float, to_int


class IndexCollector(Collector):
    name = "indexes"
    priority = 10
    description = "Indexes with type, size, event count and time span"

    def run(self) -> int:
        items: list[IndexInfo] = []
        for entry in self.client.rest_get("data/indexes", datatype="all"):
            name = entry.get("name") or ""
            if not name or (name.startswith("_") and not self.settings.include_internal_indexes):
                continue
            items.append(IndexInfo(
                name=name,
                datatype=str(entry.get("datatype") or "event"),
                event_count=to_int(entry.get("totalEventCount")),
                size_mb=to_float(entry.get("currentDBSizeMB"), 0.0) or 0.0,
                earliest=entry.get("minTime") or None,
                latest=entry.get("maxTime") or None,
                disabled=to_bool(entry.get("disabled")),
            ))
        return self.store.replace_indexes(items)

"""Hosts and sources inventory via ``tstats``."""

from __future__ import annotations

from catalog.models import EntityInfo
from discovery.base import Collector, to_float, to_int


class _EntityCollector(Collector):
    entity = ""
    limit_attr = ""

    def run(self) -> int:
        limit = getattr(self.settings, self.limit_attr)
        spl = (f"| tstats count latest(_time) AS last_seen WHERE ({self.index_filter}) BY {self.entity} "
               f"| sort - count | head {limit}")
        rows = self.client.search(spl, earliest=self.settings.lookback, latest="now", max_results=limit)
        items = [EntityInfo(self.entity, r[self.entity], to_int(r.get("count")), to_float(r.get("last_seen")))
                 for r in rows if r.get(self.entity)]
        return self.store.replace_entities(self.entity, items)


class HostCollector(_EntityCollector):
    name = "hosts"
    priority = 30
    description = "Reporting hosts"
    entity = "host"
    limit_attr = "max_hosts"


class SourceCollector(_EntityCollector):
    name = "sources"
    priority = 31
    description = "Top sources"
    entity = "source"
    limit_attr = "max_sources"

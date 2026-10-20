"""(index, sourcetype) datasets via ``tstats`` - cheap, uses indexed fields only."""

from __future__ import annotations

from catalog.models import DatasetInfo
from discovery.base import Collector, to_float, to_int


class DatasetCollector(Collector):
    name = "sourcetypes"
    priority = 20
    description = "Index/sourcetype pairs with volume and last-seen time"

    def run(self) -> int:
        spl = (f"| tstats count latest(_time) AS last_seen WHERE ({self.index_filter}) "
               f"BY index sourcetype | sort - count")
        rows = self.client.search(spl, earliest=self.settings.lookback, latest="now", max_results=50000)
        items = [DatasetInfo(index=r["index"], sourcetype=r["sourcetype"], event_count=to_int(r.get("count")),
                             last_seen=to_float(r.get("last_seen")))
                 for r in rows if r.get("index") and r.get("sourcetype")]
        return self.store.replace_datasets(items)

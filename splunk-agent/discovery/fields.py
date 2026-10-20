"""Field profiling: ``fieldsummary`` on a sample per dataset; ``mcatalog`` for metric indexes."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from catalog.models import METRICS_SOURCETYPE, FieldInfo
from core.spl import quote_value
from discovery.base import Collector, as_list, to_int

_INTERNAL = {"punct", "linecount", "timestartpos", "timeendpos", "splunk_server", "splunk_server_group",
             "eventtype", "tag", "index", "_raw", "_time", "date_hour", "date_mday", "date_minute",
             "date_month", "date_second", "date_wday", "date_year", "date_zone", "timestamp"}


class FieldCollector(Collector):
    name = "fields"
    priority = 40
    description = "Field names, coverage and sample values per dataset; metric names/dimensions"

    def run(self) -> int:
        datasets = self.store.datasets()[: self.settings.max_datasets_for_fields]
        metric_indexes = [i.name for i in self.store.metric_indexes()]
        total = 0
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=self.settings.max_workers) as pool:
            futures = {pool.submit(self._profile_dataset, d.index, d.sourcetype): (d.index, d.sourcetype)
                       for d in datasets if d.index not in metric_indexes}
            futures.update({pool.submit(self._profile_metrics, idx): (idx, METRICS_SOURCETYPE)
                            for idx in metric_indexes})
            for future in as_completed(futures):
                scope = futures[future]
                try:
                    items = future.result()
                    total += self.store.replace_fields(items, scope=scope)
                except Exception as exc:  # noqa: BLE001 - one bad dataset must not stop discovery
                    errors.append(f"{scope}: {exc}")
                    self.log.warning("Field profiling failed for %s: %s", scope, exc)
        if errors and total == 0:
            raise RuntimeError(f"Field profiling failed for all datasets ({len(errors)} errors)")
        return total

    def _profile_dataset(self, index: str, sourcetype: str) -> list[FieldInfo]:
        spl = (f"search index={quote_value(index)} sourcetype=\"{sourcetype}\" "
               f"| head {self.settings.field_sample_size} | fieldsummary maxvals=5")
        rows = self.client.search(spl, earliest=self.settings.lookback, latest="now", max_results=2000)
        sample = max((to_int(r.get("count")) for r in rows
                      if r.get("field") in ("host", "source", "sourcetype")), default=0) or \
            max((to_int(r.get("count")) for r in rows), default=1) or 1
        out: list[FieldInfo] = []
        for r in rows:
            name = r.get("field") or ""
            if not name or name in _INTERNAL or name.startswith("date_"):
                continue
            try:
                values = [str(v.get("value")) for v in json.loads(r.get("values") or "[]")][:5]
            except (TypeError, ValueError, AttributeError):
                values = []
            count = to_int(r.get("count"))
            out.append(FieldInfo(index, sourcetype, name, round(min(1.0, count / sample), 3),
                                 to_int(r.get("distinct_count")), tuple(values),
                                 to_int(r.get("numeric_count")) >= max(1, count // 2), "field"))
        return out

    def _profile_metrics(self, index: str) -> list[FieldInfo]:
        spl = f"| mcatalog values(metric_name) AS metric_name values(_dims) AS dims WHERE index={quote_value(index)}"
        rows = self.client.search(spl, earliest=self.settings.lookback, latest="now", max_results=10)
        out: list[FieldInfo] = []
        for r in rows:
            for metric in as_list(r.get("metric_name")):
                out.append(FieldInfo(index, METRICS_SOURCETYPE, str(metric), 1.0, 0, (), True, "metric"))
            for dim in as_list(r.get("dims")):
                out.append(FieldInfo(index, METRICS_SOURCETYPE, str(dim), 1.0, 0, (), False, "dimension"))
        return out

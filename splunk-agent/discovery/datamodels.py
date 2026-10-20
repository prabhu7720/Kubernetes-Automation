"""Data models with acceleration status (enables tstats variants)."""

from __future__ import annotations

import json

from catalog.models import DataModelInfo
from discovery.base import Collector, to_bool


class DataModelCollector(Collector):
    name = "datamodels"
    priority = 50
    description = "Data models, objects and acceleration"

    def run(self) -> int:
        items: list[DataModelInfo] = []
        for entry in self.client.rest_get("datamodel/model"):
            accel = entry.get("acceleration")
            if isinstance(accel, str):
                try:
                    accel = json.loads(accel)
                except ValueError:
                    accel = {"enabled": to_bool(accel)}
            objects: list[str] = []
            desc = entry.get("description")
            if isinstance(desc, str) and desc.strip().startswith("{"):
                try:
                    objects = [o.get("objectName") for o in json.loads(desc).get("objects", []) if o.get("objectName")]
                except ValueError:
                    objects = []
            items.append(DataModelInfo(entry.get("name") or "", entry.get("app"),
                                       to_bool((accel or {}).get("enabled")), tuple(objects)))
        return self.store.replace_datamodels(i for i in items if i.name)

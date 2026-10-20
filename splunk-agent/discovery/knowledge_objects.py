"""Saved searches / reports / alerts, dashboards, KV store collections and lookups."""

from __future__ import annotations

from catalog.models import KnowledgeObject
from discovery.base import Collector, to_bool


def classify_saved_search(entry: dict) -> str:
    alert_type = str(entry.get("alert_type") or "always").lower()
    actions = str(entry.get("actions") or "").strip()
    if alert_type != "always" or to_bool(entry.get("alert.track")) or actions:
        return "alert"
    if to_bool(entry.get("is_scheduled")):
        return "report"
    return "saved_search"


class SavedSearchCollector(Collector):
    name = "saved_searches"
    priority = 60
    description = "Saved searches classified as report / alert / saved_search"

    def run(self) -> int:
        items = []
        for e in self.client.rest_get("saved/searches"):
            items.append(KnowledgeObject(classify_saved_search(e), e.get("name") or "", e.get("app"), e.get("owner"), {
                "search": e.get("search"), "cron_schedule": e.get("cron_schedule"),
                "is_scheduled": to_bool(e.get("is_scheduled")), "disabled": to_bool(e.get("disabled")),
                "description": e.get("description"),
                "correlation": to_bool(e.get("action.correlationsearch.enabled")),
            }))
        return self.store.replace_knowledge_objects(("report", "alert", "saved_search"), items)


class DashboardCollector(Collector):
    name = "dashboards"
    priority = 61
    description = "Classic (Simple XML) and Dashboard Studio dashboards"

    def run(self) -> int:
        items = []
        for e in self.client.rest_get("data/ui/views"):
            if not to_bool(e.get("isDashboard", True)):
                continue
            data = str(e.get("eai:data") or "")
            items.append(KnowledgeObject("dashboard", e.get("name") or "", e.get("app"), e.get("owner"), {
                "label": e.get("label") or e.get("name"),
                "studio": 'version="2"' in data,
            }))
        return self.store.replace_knowledge_objects(("dashboard",), items)


class KVStoreCollector(Collector):
    name = "kvstore"
    priority = 62
    description = "KV store collections and their fields"

    def run(self) -> int:
        items = []
        for e in self.client.rest_get("storage/collections/config"):
            fields = sorted(k.split(".", 1)[1] for k in e if k.startswith("field."))
            accel = sorted(k.split(".", 1)[1] for k in e if k.startswith("accelerated_fields."))
            items.append(KnowledgeObject("kvstore", e.get("name") or "", e.get("app"), e.get("owner"),
                                         {"fields": fields, "accelerated_fields": accel}))
        return self.store.replace_knowledge_objects(("kvstore",), items)


class LookupCollector(Collector):
    name = "lookups"
    priority = 63
    description = "Lookup definitions (transforms) and lookup table files"

    def run(self) -> int:
        items = []
        for e in self.client.rest_get("data/transforms/lookups"):
            items.append(KnowledgeObject("lookup_definition", e.get("name") or "", e.get("app"), e.get("owner"), {
                "filename": e.get("filename"), "collection": e.get("collection"),
                "type": e.get("external_type") or ("kvstore" if e.get("collection") else "file"),
                "fields": [f.strip() for f in str(e.get("fields_list") or "").split(",") if f.strip()],
            }))
        for e in self.client.rest_get("data/lookup-table-files"):
            items.append(KnowledgeObject("lookup_file", e.get("name") or "", e.get("app"), e.get("owner"),
                                         {"path": e.get("eai:data")}))
        return self.store.replace_knowledge_objects(("lookup_definition", "lookup_file"), items)

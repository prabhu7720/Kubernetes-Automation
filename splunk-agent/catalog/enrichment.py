"""Metadata-driven enrichment: inject lookups only when a matching lookup exists in the catalog."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any, Callable, Mapping

from catalog.metadata_store import MetadataStore
from core.exceptions import TemplateRenderError


class EnrichmentResolver:
    def __init__(self, store: MetadataStore, config: Mapping[str, Mapping[str, Any]]) -> None:
        self.store = store
        self.config = dict(config)

    def find_lookup(self, name: str) -> str | None:
        cfg = self.config.get(name) or {}
        patterns = [p.lower() for p in cfg.get("lookup_patterns", [])]
        for kind in ("lookup_definition", "lookup_file"):
            for ko in self.store.knowledge_objects(kind):
                if any(fnmatchcase(ko.name.lower(), p) for p in patterns):
                    return ko.name
        return None

    def clause(self, name: str, field_resolver: Callable[[str], str]) -> str:
        cfg = self.config.get(name)
        if cfg is None:
            raise TemplateRenderError(f"Unknown enrichment '{name}' (configure it under enrichments:)")
        lookup = self.find_lookup(name)
        if not lookup:
            return ""
        event_field = field_resolver(cfg.get("event_field", "src"))
        text = f"| lookup {lookup} {cfg.get('input_field', 'ip')} AS {event_field}"
        outputs = cfg.get("outputs") or []
        return text + (f" OUTPUT {' '.join(outputs)}" if outputs else "")

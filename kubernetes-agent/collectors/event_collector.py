"""Collects Kubernetes events.

Single-resource mode uses server-side field selectors (cheap). Namespace /
deployment mode prefetches the namespace's events once and filters locally to
avoid one API call per object.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, Iterable, List, Optional

from core.k8s_utils import dig, sort_events

from .base import BaseCollector


class EventCollector(BaseCollector):
    def __init__(self, client, settings):
        super().__init__(client, settings)
        self._ns_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def prefetch_namespace(self, namespace: str, errors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if namespace in self._ns_cache:
                return self._ns_cache[namespace]
        events = self.safe(errors if errors is not None else [], f"list events in {namespace}",
                           self.client.list, "events", namespace=namespace, default=[])
        events = sort_events(events)
        with self._lock:
            self._ns_cache[namespace] = events
        return events

    def namespace_events(self, namespace: str, errors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        return self.prefetch_namespace(namespace, errors)

    def for_object(self, kind: str, name: str, namespace: Optional[str],
                   errors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        errors = errors if errors is not None else []
        if namespace and namespace in self._ns_cache:
            return [e for e in self._ns_cache[namespace]
                    if dig(e, "involvedObject", "kind") == kind and dig(e, "involvedObject", "name") == name]
        selector = f"involvedObject.kind={kind},involvedObject.name={name}"
        events = self.safe(errors, f"events for {kind} {name}", self.client.list, "events",
                           namespace=namespace, all_namespaces=namespace is None,
                           field_selector=selector, default=[])
        return sort_events(events)

    def for_objects(self, kind: str, names: Iterable[str], namespace: str,
                    errors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        wanted = set(names)
        events = self.prefetch_namespace(namespace, errors)
        return [e for e in events
                if dig(e, "involvedObject", "kind") == kind and dig(e, "involvedObject", "name") in wanted]

    def node_events(self, node_name: Optional[str] = None, errors: Optional[List[str]] = None):
        """Node events live in the 'default' namespace on most distributions; query all."""
        selector = "involvedObject.kind=Node" + (f",involvedObject.name={node_name}" if node_name else "")
        events = self.safe(errors if errors is not None else [], "list node events", self.client.list,
                           "events", all_namespaces=True, field_selector=selector, default=[])
        return sort_events(events)

"""Collects node objects, node events, metrics and per-node resource allocation."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.context import NodeContext
from core.k8s_utils import dig, pod_requests
from core.kube_client import ResourceNotFound
from core.quantity import parse_cpu, parse_memory

from .base import BaseCollector


class NodeCollector(BaseCollector):
    def __init__(self, client, settings, events):
        super().__init__(client, settings)
        self.events = events
        self._node_metrics: Optional[Dict[str, Dict[str, int]]] = None
        self._metrics_loaded = False

    def get(self, name: str, errors: List[str]) -> Optional[Dict[str, Any]]:
        return self.safe(errors, f"get node {name}", self.client.get, "node", name)

    def list(self, errors: List[str]) -> List[Dict[str, Any]]:
        return self.safe(errors, "list nodes", self.client.list, "nodes", default=[])

    def pods_on_node(self, name: str, errors: List[str]) -> List[Dict[str, Any]]:
        selector = f"spec.nodeName={name},status.phase!=Succeeded,status.phase!=Failed"
        return self.safe(errors, f"list pods on node {name}", self.client.list, "pods",
                         all_namespaces=True, field_selector=selector, default=[])

    def node_metrics(self) -> Optional[Dict[str, Dict[str, int]]]:
        if not self._metrics_loaded:
            self._node_metrics = self.client.top_nodes() if self.settings.collect_metrics else None
            self._metrics_loaded = True
        return self._node_metrics

    @staticmethod
    def allocation_from_pods(node: Dict[str, Any], pods: List[Dict[str, Any]]) -> Dict[str, Any]:
        name = dig(node, "metadata", "name")
        alloc = dig(node, "status", "allocatable") or {}
        totals = {"cpu_requests_m": 0, "memory_requests": 0, "cpu_limits_m": 0, "memory_limits": 0}
        count = 0
        for pod in pods:
            if dig(pod, "spec", "nodeName") != name or dig(pod, "status", "phase") in ("Succeeded", "Failed"):
                continue
            count += 1
            for k, v in pod_requests(pod).items():
                totals[k] += v
        return {
            **totals,
            "pods": count,
            "pods_allocatable": int(parse_memory(alloc.get("pods")) or 0),
            "cpu_allocatable_m": parse_cpu(alloc.get("cpu")) or 0,
            "memory_allocatable": parse_memory(alloc.get("memory")) or 0,
        }

    def allocation(self, name: str, errors: List[str], node: Optional[Dict[str, Any]] = None,
                   pods: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        node = node or self.get(name, errors)
        if not node:
            return None
        if pods is None:
            pods = self.pods_on_node(name, errors)
        return self.allocation_from_pods(node, pods)

    def collect(self, name: str, node: Optional[Dict[str, Any]] = None,
                all_pods: Optional[List[Dict[str, Any]]] = None,
                node_events: Optional[List[Dict[str, Any]]] = None) -> NodeContext:
        ctx = NodeContext(settings=self.settings, cmd=self.client.display_prefix())
        errs = ctx.collection_errors
        node = node or self.get(name, errs)
        if node is None:
            raise ResourceNotFound(f"Node {name} not found")
        ctx.node = node
        if all_pods is not None:
            ctx.pods = [p for p in all_pods if dig(p, "spec", "nodeName") == name]
        else:
            ctx.pods = self.pods_on_node(name, errs)
        ctx.allocation = self.allocation_from_pods(node, ctx.pods)
        if node_events is not None:
            ctx.events = [e for e in node_events if dig(e, "involvedObject", "name") == name]
        else:
            ctx.events = self.events.node_events(name, errs)
        metrics = self.node_metrics()
        ctx.metrics = (metrics or {}).get(name)
        return ctx

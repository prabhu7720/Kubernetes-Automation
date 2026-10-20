"""Collects namespace-wide and cluster-wide inventories in as few API calls as possible."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.context import ClusterContext, NamespaceContext
from core.kube_client import KubectlError, ResourceNotFound

from .base import BaseCollector

CERT_RESOURCE = "certificates.cert-manager.io"


class ClusterCollector(BaseCollector):
    def __init__(self, client, settings, events, nodes, storage):
        super().__init__(client, settings)
        self.events = events
        self.nodes = nodes
        self.storage = storage

    def certificates(self, errors: List[str], namespace: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """cert-manager Certificates, or None when the CRD isn't installed."""
        try:
            return self.client.list(CERT_RESOURCE, namespace=namespace, all_namespaces=namespace is None)
        except KubectlError as exc:
            if exc.unknown_resource or exc.not_found:
                return None
            errors.append(self.describe_error("list cert-manager certificates", exc))
            return None

    def namespace(self, name: str) -> NamespaceContext:
        ns_obj = self.client.get("namespace", name)
        if ns_obj is None:
            raise ResourceNotFound(f"Namespace {name} not found")
        ctx = NamespaceContext(settings=self.settings, cmd=self.client.display_prefix(), namespace_obj=ns_obj)
        errs = ctx.collection_errors
        ctx.events = self.events.prefetch_namespace(name, errs)
        ctx.pods = self.safe(errs, "list pods", self.client.list, "pods", namespace=name, default=[])
        ctx.deployments = self.safe(errs, "list deployments", self.client.list, "deployments", namespace=name, default=[])
        ctx.replicasets = self.safe(errs, "list replicasets", self.client.list, "replicasets", namespace=name, default=[])
        ctx.pvcs = self.safe(errs, "list pvcs", self.client.list, "persistentvolumeclaims", namespace=name, default=[])
        ctx.quotas = self.safe(errs, "list resourcequotas", self.client.list, "resourcequotas", namespace=name, default=[])
        ctx.storage_classes = self.storage.storage_classes(errs) if ctx.pvcs else {}
        ctx.certificates = self.certificates(errs, namespace=name)
        return ctx

    def cluster(self) -> ClusterContext:
        ctx = ClusterContext(settings=self.settings, cmd=self.client.display_prefix())
        errs = ctx.collection_errors
        ctx.context_name = self.client.current_context()
        ctx.server_version = self.client.server_version()
        ctx.nodes = self.nodes.list(errs)
        ctx.pods = self.safe(errs, "list pods (all namespaces)", self.client.list, "pods",
                             all_namespaces=True, default=[])
        ctx.deployments = self.safe(errs, "list deployments (all namespaces)", self.client.list,
                                    "deployments", all_namespaces=True, default=[])
        ctx.certificates = self.certificates(errs)
        ctx.node_metrics = self.nodes.node_metrics()
        return ctx

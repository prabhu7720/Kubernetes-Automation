"""Collects everything needed to diagnose a single pod.

Gathered data (requirement #4):
  pod status / restart counts / container states   -> pod object
  "describe" equivalent                            -> pod object + events
  previous and current container logs              -> kubectl logs [--previous]
  events                                           -> EventCollector
  owner chain + deployment details                 -> DeploymentCollector
  requests/limits + live usage                     -> pod spec + kubectl top
  node information + node allocation               -> NodeCollector
  PVC / PV / StorageClass status                   -> StorageCollector
  service account                                  -> kubectl get serviceaccount
  secret/configmap existence (names only)          -> server-side table output
"""
from __future__ import annotations

from typing import Any, Dict

from core.context import PodContext
from core.k8s_utils import dig
from core.kube_client import KubectlError, ResourceNotFound
from core.refs import configmap_references, image_pull_secret_names, secret_references

from .base import BaseCollector


class PodCollector(BaseCollector):
    def __init__(self, client, settings, events, nodes, deployments, storage):
        super().__init__(client, settings)
        self.events = events
        self.nodes = nodes
        self.deployments = deployments
        self.storage = storage
        self._allocation_cache: Dict[str, Any] = {}

    def collect(self, name: str, namespace: str) -> PodContext:
        pod = self.client.get("pod", name, namespace)
        if pod is None:
            raise ResourceNotFound(f"Pod {namespace}/{name} not found")
        return self.from_object(pod)

    def from_object(self, pod: Dict[str, Any]) -> PodContext:
        ctx = PodContext(settings=self.settings, cmd=self.client.display_prefix(), pod=pod)
        errs = ctx.collection_errors
        ns, name = ctx.namespace, ctx.name

        ctx.events = self.events.for_object("Pod", name, ns, errs)
        if self.settings.collect_logs:
            self._collect_logs(ctx)
        ctx.owners, ctx.deployment = self.deployments.resolve_owners(pod, errs)
        self._collect_node(ctx)
        self.storage.populate_pod(ctx)
        self._collect_service_account(ctx)
        self._collect_config_refs(ctx)
        if self.settings.collect_metrics and ctx.phase == "Running":
            ctx.metrics = self.client.top_pod(name, ns)
        return ctx

    # ------------------------------------------------------------------ steps
    def _collect_logs(self, ctx: PodContext) -> None:
        tail = self.settings.log_tail_lines
        for st in ctx.statuses():
            cname = st.get("name")
            state = st.get("state") or {}
            has_previous = (st.get("restartCount") or 0) > 0 or bool(dig(st, "lastState", "terminated"))
            if state.get("running") or state.get("terminated") or has_previous:
                text = self.safe(ctx.collection_errors, f"logs {cname}", self.client.logs,
                                 ctx.name, ctx.namespace, cname, previous=False, tail=tail)
                if text:
                    ctx.logs_current[cname] = text
            if has_previous:
                text = self.safe(ctx.collection_errors, f"previous logs {cname}", self.client.logs,
                                 ctx.name, ctx.namespace, cname, previous=True, tail=tail)
                if text:
                    ctx.logs_previous[cname] = text

    def _collect_node(self, ctx: PodContext) -> None:
        node_name = ctx.node_name
        if not node_name:
            return
        ctx.node = self.nodes.get(node_name, ctx.collection_errors)
        if ctx.node is None:
            return
        if node_name not in self._allocation_cache:
            self._allocation_cache[node_name] = self.nodes.allocation(node_name, ctx.collection_errors, node=ctx.node)
        ctx.node_allocation = self._allocation_cache[node_name]

    def _collect_service_account(self, ctx: PodContext) -> None:
        sa = ctx.spec.get("serviceAccountName") or ctx.spec.get("serviceAccount") or "default"
        ctx.service_account_name = sa
        try:
            ctx.service_account = self.client.get("serviceaccount", sa, ctx.namespace)
            ctx.service_account_checked = True
        except KubectlError as exc:
            ctx.collection_errors.append(self.describe_error(f"get serviceaccount {sa}", exc))

    def _collect_config_refs(self, ctx: PodContext) -> None:
        needs_secrets = bool(secret_references(ctx.pod)) or bool(image_pull_secret_names(ctx.pod)) \
            or bool((ctx.service_account or {}).get("imagePullSecrets"))
        if needs_secrets:
            ctx.secret_names = self.safe(ctx.collection_errors, "list secret names", self.client.resource_names,
                                         "secrets", ctx.namespace)
        if configmap_references(ctx.pod):
            ctx.configmap_names = self.safe(ctx.collection_errors, "list configmap names",
                                            self.client.resource_names, "configmaps", ctx.namespace)

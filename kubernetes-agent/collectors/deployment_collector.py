"""Collects deployments, their ReplicaSets/pods, and resolves pod owner chains."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.context import DeploymentContext
from core.k8s_utils import controller_ref, dig, selector_to_string
from core.kube_client import ResourceNotFound

from .base import BaseCollector

KIND_TO_RESOURCE = {
    "ReplicaSet": "replicaset", "Deployment": "deployment", "StatefulSet": "statefulset",
    "DaemonSet": "daemonset", "Job": "job", "CronJob": "cronjob",
    "ReplicationController": "replicationcontroller",
}


class DeploymentCollector(BaseCollector):
    def __init__(self, client, settings, events):
        super().__init__(client, settings)
        self.events = events

    def get(self, name: str, namespace: str) -> Optional[Dict[str, Any]]:
        return self.client.get("deployment", name, namespace)

    def resolve_owners(self, obj: Dict[str, Any], errors: List[str]) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Walk ownerReferences upward: Pod -> ReplicaSet -> Deployment (or STS/DS/Job/CronJob)."""
        namespace = dig(obj, "metadata", "namespace")
        chain: List[Dict[str, Any]] = []
        deployment = None
        ref = controller_ref(obj)
        depth = 0
        while ref and depth < 4:
            depth += 1
            kind, name = ref.get("kind"), ref.get("name")
            resource = KIND_TO_RESOURCE.get(kind)
            stub = {"kind": kind, "metadata": {"name": name, "namespace": namespace}}
            if not resource:
                chain.append(stub)
                break
            owner = self.safe(errors, f"get {kind} {name}", self.client.get, resource, name, namespace)
            if owner is None:
                stub["_missing"] = True
                chain.append(stub)
                break
            owner.setdefault("kind", kind)
            chain.append(owner)
            if kind == "Deployment":
                deployment = owner
            ref = controller_ref(owner)
        return chain, deployment

    def build_context(self, deployment: Dict[str, Any], replicasets: List[Dict[str, Any]],
                      pods: List[Dict[str, Any]], events: List[Dict[str, Any]],
                      quotas: Optional[List[Dict[str, Any]]] = None,
                      hpas: Optional[List[Dict[str, Any]]] = None) -> DeploymentContext:
        """Assemble a DeploymentContext from already-fetched lists (namespace mode reuses this)."""
        uid = dig(deployment, "metadata", "uid")
        name = dig(deployment, "metadata", "name")
        owned_rs = [rs for rs in replicasets
                    if any(o.get("uid") == uid for o in dig(rs, "metadata", "ownerReferences") or [])]
        rs_uids = {dig(rs, "metadata", "uid") for rs in owned_rs}
        owned_pods = [p for p in pods
                      if any(o.get("uid") in rs_uids for o in dig(p, "metadata", "ownerReferences") or [])]
        rs_names = {dig(rs, "metadata", "name") for rs in owned_rs}
        dep_events = [e for e in events if
                      (dig(e, "involvedObject", "kind") == "Deployment" and dig(e, "involvedObject", "name") == name)
                      or (dig(e, "involvedObject", "kind") == "ReplicaSet" and dig(e, "involvedObject", "name") in rs_names)]
        hpa = next((h for h in hpas or [] if dig(h, "spec", "scaleTargetRef", "kind") == "Deployment"
                    and dig(h, "spec", "scaleTargetRef", "name") == name), None)
        ctx = DeploymentContext(settings=self.settings, cmd=self.client.display_prefix(),
                                deployment=deployment, replicasets=owned_rs, pods=owned_pods,
                                events=dep_events, quotas=list(quotas or []), hpa=hpa)
        return ctx

    def collect(self, name: str, namespace: str) -> DeploymentContext:
        deployment = self.get(name, namespace)
        if deployment is None:
            raise ResourceNotFound(f"Deployment {namespace}/{name} not found")
        errs: List[str] = []
        selector = selector_to_string(dig(deployment, "spec", "selector"))
        replicasets = self.safe(errs, "list replicasets", self.client.list, "replicasets",
                                namespace=namespace, label_selector=selector or None, default=[])
        pods = self.safe(errs, "list pods", self.client.list, "pods", namespace=namespace,
                         label_selector=selector or None, default=[])
        events = self.events.prefetch_namespace(namespace, errs)
        quotas = self.safe(errs, "list resourcequotas", self.client.list, "resourcequotas",
                           namespace=namespace, default=[])
        hpas = self.safe(errs, "list hpa", self.client.list, "horizontalpodautoscalers",
                         namespace=namespace, default=[])
        ctx = self.build_context(deployment, replicasets, pods, events, quotas, hpas)
        ctx.collection_errors.extend(errs)
        return ctx

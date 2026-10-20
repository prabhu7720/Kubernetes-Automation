"""Namespace, node and cluster analyzers.

Namespace mode groups unhealthy pods under their owning Deployment so the
report reads top-down: Deployment -> its failing pods -> root causes.
Cluster mode evaluates every node, cluster-level components, and the most
severe unhealthy pods across all namespaces.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from core.k8s_utils import controller_ref, dig, node_pressures, node_ready, pod_health
from core.models import AnalysisResult

from .base import BaseAnalyzer
from .deployment_analyzer import DeploymentAnalyzer
from .pod_analyzer import PodAnalyzer


def _phase_counts(pods: List[Dict[str, Any]]) -> str:
    counts = Counter(dig(p, "status", "phase", default="Unknown") for p in pods)
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none"


class NamespaceAnalyzer(BaseAnalyzer):
    def __init__(self, *args, pod_analyzer: PodAnalyzer, deployment_analyzer: DeploymentAnalyzer, **kwargs):
        super().__init__(*args, **kwargs)
        self.pod_analyzer = pod_analyzer
        self.deployment_analyzer = deployment_analyzer

    def analyze(self, namespace: str) -> AnalysisResult:
        ctx = self.collectors.cluster.namespace(namespace)
        findings = self.run_rules(ctx)
        result = AnalysisResult(resource=ctx.ref, findings=findings, collection_errors=list(ctx.collection_errors))

        threshold = self.settings.restart_threshold
        scored = []
        for pod in ctx.pods:
            bad, _, score = pod_health(pod, threshold)
            if bad:
                scored.append((score, pod))
        scored.sort(key=lambda x: -x[0])
        selected = [p for _, p in scored[: self.settings.max_pods_per_namespace]]
        pod_results = self.parallel(self.pod_analyzer.analyze_object, selected)
        pod_by_uid = {dig(p, "metadata", "uid"): r for p, r in zip(selected, pod_results)}

        # map pods -> deployments through ReplicaSets
        rs_owner = {}
        for rs in ctx.replicasets:
            ref = controller_ref(rs)
            if ref and ref.get("kind") == "Deployment":
                rs_owner[dig(rs, "metadata", "uid")] = ref.get("name")
        pods_by_deploy: Dict[str, List[AnalysisResult]] = defaultdict(list)
        standalone: List[AnalysisResult] = []
        for pod in selected:
            ref = controller_ref(pod) or {}
            dep = rs_owner.get(ref.get("uid")) if ref.get("kind") == "ReplicaSet" else None
            (pods_by_deploy[dep] if dep else standalone).append(pod_by_uid[dig(pod, "metadata", "uid")])

        unavailable = []
        for dep in ctx.deployments:
            name = dig(dep, "metadata", "name")
            desired = dig(dep, "spec", "replicas", default=1)
            available = dig(dep, "status", "availableReplicas", default=0)
            if name not in pods_by_deploy and (desired == 0 or available >= desired):
                continue
            if available < desired:
                unavailable.append(f"{name} ({available}/{desired})")
            dctx = self.collectors.deployments.build_context(dep, ctx.replicasets, ctx.pods, ctx.events, ctx.quotas)
            dres = self.deployment_analyzer.analyze_context(dctx, drill_down=False)
            dres.children = pods_by_deploy.get(name, [])
            result.children.append(dres)
        result.children.extend(standalone)

        result.facts = [
            f"Pods: {len(ctx.pods)} ({_phase_counts(ctx.pods)})",
            f"Unhealthy pods: {len(scored)} (analyzed {len(selected)})",
            f"Deployments: {len(ctx.deployments)}, unavailable: {', '.join(unavailable) or 'none'}",
            f"PVCs: {len(ctx.pvcs)} ({_phase_counts(ctx.pvcs)})",
            f"ResourceQuotas: {len(ctx.quotas)}",
            f"Warning events: {sum(1 for e in ctx.events if e.get('type') == 'Warning')}",
        ]
        return result


class NodeAnalyzer(BaseAnalyzer):
    def __init__(self, *args, pod_analyzer: PodAnalyzer, **kwargs):
        super().__init__(*args, **kwargs)
        self.pod_analyzer = pod_analyzer

    def analyze(self, name: str, drill_down: bool = True, **collect_kwargs) -> AnalysisResult:
        ctx = self.collectors.nodes.collect(name, **collect_kwargs)
        findings = self.run_rules(ctx)
        result = AnalysisResult(resource=ctx.ref, findings=findings, facts=self.facts(ctx),
                                collection_errors=list(ctx.collection_errors))
        if drill_down:
            bad = sorted(((pod_health(p, self.settings.restart_threshold), p) for p in ctx.pods),
                         key=lambda x: -x[0][2])
            selected = [p for (h, p) in bad if h[0]][: self.settings.max_pods_per_namespace]
            result.children = self.parallel(self.pod_analyzer.analyze_object, selected)
        return result

    @staticmethod
    def facts(ctx) -> List[str]:
        node = ctx.node
        info = dig(node, "status", "nodeInfo") or {}
        alloc = ctx.allocation or {}
        facts = [f"Ready: {node_ready(node)}; pressure: {', '.join(node_pressures(node)) or 'none'}"
                 + ("; cordoned" if dig(node, "spec", "unschedulable") else ""),
                 f"Kubelet: {info.get('kubeletVersion')}  runtime: {info.get('containerRuntimeVersion')}  "
                 f"OS: {info.get('osImage')}  arch: {info.get('architecture')}",
                 f"Pods: {alloc.get('pods')}/{alloc.get('pods_allocatable')}"]
        labels = dig(node, "metadata", "labels") or {}
        for key in ("node.kubernetes.io/instance-type", "topology.kubernetes.io/zone",
                    "eks.amazonaws.com/nodegroup", "cloud.google.com/gke-nodepool", "kubernetes.azure.com/agentpool"):
            if key in labels:
                facts.append(f"{key}: {labels[key]}")
        if ctx.metrics:
            from core.quantity import format_bytes, format_cpu
            facts.append(f"Usage: cpu={format_cpu(ctx.metrics['cpu_m'])} memory={format_bytes(ctx.metrics['memory_bytes'])}")
        return facts


class ClusterAnalyzer(BaseAnalyzer):
    def __init__(self, *args, pod_analyzer: PodAnalyzer, node_analyzer: NodeAnalyzer, **kwargs):
        super().__init__(*args, **kwargs)
        self.pod_analyzer = pod_analyzer
        self.node_analyzer = node_analyzer

    def analyze(self) -> AnalysisResult:
        ctx = self.collectors.cluster.cluster()
        findings = self.run_rules(ctx)
        result = AnalysisResult(resource=ctx.ref, findings=findings, collection_errors=list(ctx.collection_errors))

        node_events = self.collectors.events.node_events(None, result.collection_errors)
        node_results = [self.node_analyzer.analyze(n["metadata"]["name"], drill_down=False, node=n,
                                                   all_pods=ctx.pods, node_events=node_events) for n in ctx.nodes]

        scored = []
        for pod in ctx.pods:
            bad, _, score = pod_health(pod, self.settings.restart_threshold)
            if bad:
                scored.append((score, pod))
        scored.sort(key=lambda x: -x[0])
        selected = [p for _, p in scored[: self.settings.max_pods_cluster]]
        for ns in sorted({dig(p, "metadata", "namespace") for p in selected}):
            self.collectors.events.prefetch_namespace(ns, result.collection_errors)
        pod_results = self.parallel(self.pod_analyzer.analyze_object, selected)

        result.children = [r for r in node_results if r.findings] + pod_results
        ready = sum(1 for n in ctx.nodes if node_ready(n))
        unavailable = [f"{dig(d, 'metadata', 'namespace')}/{dig(d, 'metadata', 'name')}"
                       for d in ctx.deployments
                       if dig(d, "status", "availableReplicas", default=0) < dig(d, "spec", "replicas", default=1)]
        result.facts = [
            f"Context: {ctx.context_name}  Server version: {ctx.server_version}",
            f"Nodes: {len(ctx.nodes)} (Ready={ready}, NotReady={len(ctx.nodes) - ready})",
            f"Pods: {len(ctx.pods)} ({_phase_counts(ctx.pods)})",
            f"Unhealthy pods: {len(scored)} (analyzed {len(selected)})",
            f"Namespaces with unhealthy pods: {len({dig(p, 'metadata', 'namespace') for _, p in scored})}",
            f"Deployments with unavailable replicas: {len(unavailable)}" +
            (f" ({', '.join(unavailable[:10])}{' ...' if len(unavailable) > 10 else ''})" if unavailable else ""),
            "cert-manager: " + ("not installed" if ctx.certificates is None else f"{len(ctx.certificates)} certificates"),
        ]
        healthy_nodes = [r.resource.name for r in node_results if not r.findings]
        if healthy_nodes:
            result.facts.append(f"Healthy nodes: {len(healthy_nodes)}")
        return result

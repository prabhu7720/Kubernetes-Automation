"""Cluster-level rules: health of kube-system components (CoreDNS, CNI, proxies, CSI...)."""
from __future__ import annotations

from collections import defaultdict

from core.k8s_utils import dig, pod_health
from core.models import ResourceRef, Scope, Severity

from .base import Rule


def _component(pod) -> str:
    labels = dig(pod, "metadata", "labels") or {}
    for key in ("k8s-app", "app.kubernetes.io/name", "component", "app", "name"):
        if labels.get(key):
            return labels[key]
    return (dig(pod, "metadata", "generateName") or dig(pod, "metadata", "name") or "?").rstrip("-")


class SystemComponentRule(Rule):
    id = "K8S-CLUS-001"
    name = "Unhealthy kube-system components"
    category = "cluster"
    scopes = (Scope.CLUSTER,)

    def evaluate(self, ctx):
        threshold = int(self.setting("restart_threshold", 3))
        groups = defaultdict(lambda: {"total": 0, "bad": []})
        for pod in ctx.kube_system_pods:
            comp = _component(pod)
            groups[comp]["total"] += 1
            unhealthy, reasons, _ = pod_health(pod, threshold)
            if unhealthy:
                groups[comp]["bad"].append((dig(pod, "metadata", "name"), reasons, dig(pod, "spec", "nodeName")))
        findings = []
        for comp, info in sorted(groups.items()):
            bad = info["bad"]
            if not bad:
                continue
            is_dns = comp in ("kube-dns", "coredns")
            all_down = len(bad) == info["total"]
            sev = Severity.CRITICAL if is_dns and all_down else Severity.HIGH if (is_dns or all_down) else Severity.MEDIUM
            impact = (" Cluster DNS is degraded: workloads will see name resolution failures." if is_dns else "")
            findings.append(self.finding(
                ctx, resource=ResourceRef("Component", comp, "kube-system"),
                title=f"kube-system component unhealthy: {comp}", severity=sev,
                root_cause=f"{len(bad)}/{info['total']} '{comp}' pods in kube-system are unhealthy.{impact}",
                evidence=[f"{n} on {node or '-'}: {', '.join(r)}" for n, r, node in bad[:6]], confidence=90,
                recommendations=[f"Analyze the failing pods: python agent.py analyze pod {bad[0][0]} -n kube-system",
                                 "If they are DaemonSet pods, check whether failures are limited to specific nodes."],
                commands=[f"{ctx.cmd} get pods -n kube-system -o wide | grep {comp}",
                          f"{ctx.cmd} describe pod {bad[0][0]} -n kube-system"]))
        return findings

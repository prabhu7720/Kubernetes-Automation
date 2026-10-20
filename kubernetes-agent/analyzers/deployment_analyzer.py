"""Deployment analyzer: DEPLOYMENT rules + drill-down into the most unhealthy pods."""
from __future__ import annotations

from typing import Any, Dict, List

from core.context import DeploymentContext
from core.k8s_utils import conditions_map, dig, pod_health
from core.models import AnalysisResult

from .base import BaseAnalyzer
from .pod_analyzer import PodAnalyzer


class DeploymentAnalyzer(BaseAnalyzer):
    def __init__(self, *args, pod_analyzer: PodAnalyzer, **kwargs):
        super().__init__(*args, **kwargs)
        self.pod_analyzer = pod_analyzer

    def analyze(self, name: str, namespace: str) -> AnalysisResult:
        return self.analyze_context(self.collectors.deployments.collect(name, namespace))

    def unhealthy_pods(self, pods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        scored = []
        for pod in pods:
            bad, _, score = pod_health(pod, self.settings.restart_threshold)
            if bad:
                scored.append((score, pod))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored]

    def analyze_context(self, ctx: DeploymentContext, drill_down: bool = True) -> AnalysisResult:
        findings = self.run_rules(ctx)
        result = AnalysisResult(resource=ctx.ref, facts=self.facts(ctx), findings=findings,
                                collection_errors=list(ctx.collection_errors))
        if drill_down:
            unhealthy = self.unhealthy_pods(ctx.pods)
            selected = unhealthy[: self.settings.max_pods_per_deployment]
            result.children = self.parallel(self.pod_analyzer.analyze_object, selected)
            if len(unhealthy) > len(selected):
                result.facts.append(f"Pods analyzed: {len(selected)} of {len(unhealthy)} unhealthy "
                                    "(raise max_pods_per_deployment to see more)")
        return result

    @staticmethod
    def facts(ctx: DeploymentContext) -> List[str]:
        dep = ctx.deployment
        st = dep.get("status") or {}
        strategy = dig(dep, "spec", "strategy", "type", default="RollingUpdate")
        facts = [f"Replicas: desired={dig(dep, 'spec', 'replicas', default=1)} updated={st.get('updatedReplicas', 0)} "
                 f"ready={st.get('readyReplicas', 0)} available={st.get('availableReplicas', 0)}",
                 f"Strategy: {strategy}" + (f" (maxSurge={dig(dep, 'spec', 'strategy', 'rollingUpdate', 'maxSurge')}, "
                                            f"maxUnavailable={dig(dep, 'spec', 'strategy', 'rollingUpdate', 'maxUnavailable')})"
                                            if strategy == "RollingUpdate" else ""),
                 f"Revision: {dig(dep, 'metadata', 'annotations', 'deployment.kubernetes.io/revision')}",
                 "Images: " + ", ".join(c.get("image", "?") for c in dig(dep, "spec", "template", "spec", "containers") or [])]
        for ctype, cond in conditions_map(dep).items():
            facts.append(f"Condition {ctype}={cond.get('status')} ({cond.get('reason')})")
        current = ctx.current_replicaset()
        if current:
            facts.append(f"Current ReplicaSet: {dig(current, 'metadata', 'name')} "
                         f"(ready {dig(current, 'status', 'readyReplicas', default=0)}/{dig(current, 'spec', 'replicas', default=0)})")
        phases: Dict[str, int] = {}
        for p in ctx.pods:
            ph = dig(p, "status", "phase", default="Unknown")
            phases[ph] = phases.get(ph, 0) + 1
        facts.append(f"Pods: {len(ctx.pods)} " + (str(phases) if phases else ""))
        if ctx.hpa:
            facts.append(f"HPA: {dig(ctx.hpa, 'metadata', 'name')} min={dig(ctx.hpa, 'spec', 'minReplicas')} "
                         f"max={dig(ctx.hpa, 'spec', 'maxReplicas')}")
        return facts

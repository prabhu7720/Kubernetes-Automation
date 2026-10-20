"""Pod analyzer: collects a PodContext, runs POD rules, and builds the fact summary."""
from __future__ import annotations

from typing import Any, Dict, List

from core.context import PodContext
from core.k8s_utils import dig, node_summary, resources_line
from core.models import AnalysisResult
from core.quantity import format_bytes, format_cpu

from .base import BaseAnalyzer


class PodAnalyzer(BaseAnalyzer):
    def analyze(self, name: str, namespace: str) -> AnalysisResult:
        return self.analyze_context(self.collectors.pods.collect(name, namespace))

    def analyze_object(self, pod: Dict[str, Any]) -> AnalysisResult:
        try:
            ctx = self.collectors.pods.from_object(pod)
        except Exception as exc:  # keep namespace/cluster runs going
            self.log.exception("pod collection failed")
            from core.models import ResourceRef
            return AnalysisResult(resource=ResourceRef("Pod", dig(pod, "metadata", "name"), dig(pod, "metadata", "namespace")),
                                  collection_errors=[f"collection failed: {exc}"])
        return self.analyze_context(ctx)

    def analyze_context(self, ctx: PodContext) -> AnalysisResult:
        findings = self.run_rules(ctx)
        return AnalysisResult(resource=ctx.ref, facts=self.facts(ctx), findings=findings,
                              collection_errors=list(ctx.collection_errors))

    @staticmethod
    def facts(ctx: PodContext) -> List[str]:
        ready = sum(1 for s in ctx.statuses(False) if s.get("ready"))
        total = len(ctx.statuses(False)) or len(ctx.containers(False))
        facts = [f"Phase: {ctx.phase} ({ready}/{total} containers ready)" +
                 (f", reason: {ctx.status['reason']}" if ctx.status.get("reason") else ""),
                 f"Restart count: {ctx.total_restarts()}"]
        owner = ctx.owner_label()
        if owner:
            facts.append(f"Owner: {owner}")
        if ctx.deployment:
            st = ctx.deployment.get("status") or {}
            facts.append(f"Deployment replicas: desired={dig(ctx.deployment, 'spec', 'replicas', default=1)} "
                         f"available={st.get('availableReplicas', 0)} updated={st.get('updatedReplicas', 0)}")
        facts.append(f"Node: {ctx.node_name} ({node_summary(ctx.node)})" if ctx.node_name else "Node: not scheduled")
        facts.append(f"QoS class: {ctx.status.get('qosClass', 'unknown')}")
        for st in ctx.statuses():
            cname = st.get("name")
            kind = "init container" if cname in ctx.init_container_names() else "container"
            state = st.get("state") or {}
            state_s = next(iter(state.keys()), "unknown")
            detail = dig(state, state_s, "reason")
            line = f"{kind} {cname}: {state_s}{f' ({detail})' if detail else ''}, restarts={st.get('restartCount', 0)}"
            last = dig(st, "lastState", "terminated")
            if last:
                line += f", last termination: {last.get('reason')} (exit {last.get('exitCode')}) at {last.get('finishedAt')}"
            facts.append(line)
            spec = ctx.spec_of(cname) or {}
            facts.append(f"  image: {spec.get('image')}")
            facts.append(f"  resources: {resources_line(spec)}")
            usage = (ctx.metrics or {}).get(cname)
            if usage:
                facts.append(f"  usage: cpu={format_cpu(usage['cpu_m'])} memory={format_bytes(usage['memory_bytes'])}")
        for claim, pvc in ctx.pvcs.items():
            if pvc is None:
                facts.append(f"PVC {claim}: MISSING")
            else:
                facts.append(f"PVC {claim}: {dig(pvc, 'status', 'phase')} (pv={dig(pvc, 'spec', 'volumeName')}, "
                             f"{dig(pvc, 'status', 'capacity', 'storage') or dig(pvc, 'spec', 'resources', 'requests', 'storage')}, "
                             f"sc={dig(pvc, 'spec', 'storageClassName')})")
        if ctx.service_account_checked:
            facts.append(f"Service account: {ctx.service_account_name} "
                         f"({'exists' if ctx.service_account else 'MISSING'})")
        else:
            facts.append(f"Service account: {ctx.service_account_name} (not verified)")
        warnings = [e for e in ctx.events if e.get("type") == "Warning"]
        facts.append(f"Events: {len(ctx.events)} total, {len(warnings)} warnings")
        logs = [c for c in ctx.logs_previous] or []
        facts.append(f"Logs collected: current={sorted(ctx.logs_current)} previous={sorted(logs)}")
        return facts

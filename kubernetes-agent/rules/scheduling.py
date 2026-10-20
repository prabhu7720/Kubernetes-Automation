"""FailedScheduling analysis: parses the scheduler's per-predicate breakdown."""
from __future__ import annotations

import re
from typing import List, Tuple

from core.k8s_utils import conditions_map, format_event, pod_requests
from core.models import Finding, Scope, Severity
from core.quantity import format_bytes, format_cpu

from ._common import describe_cmd, events_cmd
from .base import Rule

# (pattern, explanation template, recommendations)
CAUSES: List[Tuple[str, str, List[str]]] = [
    (r"Insufficient ([\w./-]+)",
     "not enough allocatable {0} for the pod's requests",
     ["Lower the pod's requests to realistic values, or add capacity (scale node group / cluster autoscaler).",
      "Check allocated resources per node: kubectl describe nodes | grep -A8 'Allocated resources'."]),
    (r"untolerated taint \{?([^}]*)\}?",
     "node taint not tolerated by the pod ({0})",
     ["Add a matching toleration to the pod, or target the intended node pool.",
      "If the taint is node.kubernetes.io/not-ready|unreachable|*-pressure, fix the node health instead."]),
    (r"didn't match Pod's node affinity/selector|didn't match node selector",
     "nodeSelector / nodeAffinity matches no available node",
     ["Compare pod nodeSelector/affinity with node labels: kubectl get nodes --show-labels."]),
    (r"didn't match pod (anti-)?affinity rules|didn't satisfy existing pods anti-affinity rules",
     "pod affinity / anti-affinity constraints cannot be satisfied",
     ["Relax required anti-affinity to preferred, or add nodes/zones so replicas can spread."]),
    (r"didn't match pod topology spread constraints",
     "topologySpreadConstraints cannot be satisfied",
     ["Use whenUnsatisfiable: ScheduleAnyway or increase maxSkew / available zones."]),
    (r"volume node affinity conflict",
     "the PersistentVolume is bound to a zone/node where the pod cannot run",
     ["Use volumeBindingMode: WaitForFirstConsumer and ensure nodes exist in the PV's zone."]),
    (r"unbound immediate PersistentVolumeClaims|persistentvolumeclaim \"[^\"]+\" not found",
     "the pod's PVC is not bound (or missing)",
     ["Fix the PVC first (see PVC findings): kubectl describe pvc -n <ns>."]),
    (r"were unschedulable|node\(s\) were unschedulable",
     "nodes are cordoned (unschedulable)",
     ["Uncordon nodes after maintenance: kubectl uncordon <node>."]),
    (r"Too many pods", "nodes reached their max-pods limit",
     ["Increase max pods per node (CNI/IP limits permitting) or add nodes."]),
    (r"didn't have free ports", "requested hostPort is already used on the nodes",
     ["Avoid hostPort or ensure one pod per node via DaemonSet / anti-affinity."]),
    (r"exceed max volume count", "nodes reached their maximum attachable volumes",
     ["Use larger instance types or spread volume-heavy pods."]),
    (r"0/0 nodes are available|no nodes available", "the cluster has no schedulable nodes",
     ["Check node groups / autoscaler; kubectl get nodes."]),
]


class FailedSchedulingRule(Rule):
    id = "K8S-SCHED-001"
    name = "FailedScheduling"
    category = "scheduling"
    scopes = (Scope.POD,)

    @staticmethod
    def parse(message: str) -> Tuple[List[str], List[str]]:
        """'0/5 nodes are available: 2 Insufficient memory, 3 node(s) had untolerated taint {k: v}.'"""
        summary = (message or "").split(" preemption:")[0].strip().rstrip(".")
        body = summary.split(": ", 1)[1] if re.match(r"^\d+/\d+ nodes are available: ", summary) else summary
        causes: List[str] = []
        recs: List[str] = []
        for item in re.split(r",\s+(?=\d+ )", body):
            m = re.match(r"^(\d+)\s+(.*)$", item.strip())
            count, text = (m.group(1), m.group(2)) if m else (None, item.strip())
            for pattern, template, rec in CAUSES:
                pm = re.search(pattern, text, re.I)
                if pm:
                    groups = [g for g in pm.groups() if g] or [""]
                    causes.append((f"{count} node(s) - " if count else "") + template.format(*groups).strip())
                    recs.extend(rec)
                    break
        if not causes:
            for pattern, template, rec in CAUSES:   # unstructured message fallback
                pm = re.search(pattern, summary, re.I)
                if pm:
                    causes.append(template.format(*([g for g in pm.groups() if g] or [""])))
                    recs.extend(rec)
        return list(dict.fromkeys(causes)), list(dict.fromkeys(recs))

    def evaluate(self, ctx) -> List[Finding]:
        cond =conditions_map(ctx.pod).get("PodScheduled") or {}
        unschedulable = cond.get("status") == "False"
        events = ctx.events_with_reason("FailedScheduling")
        if not unschedulable and not (events and ctx.phase == "Pending" and not ctx.node_name):
            return []
        message = (events[-1].get("message") if events else "") or cond.get("message") or ""
        causes, recs = self.parse(message)
        req = pod_requests(ctx.pod)
        evidence = [f"Pod phase: {ctx.phase}",
                    f"PodScheduled: {cond.get('status', '?')} ({cond.get('reason', '')})",
                    f"Scheduler message: {' '.join(message.split())[:400]}",
                    f"Pod requests: cpu={format_cpu(req['cpu_requests_m'])} memory={format_bytes(req['memory_requests'])}"]
        if ctx.spec.get("nodeSelector"):
            evidence.append(f"nodeSelector: {ctx.spec['nodeSelector']}")
        if ctx.spec.get("tolerations"):
            evidence.append(f"tolerations: {[t.get('key') for t in ctx.spec['tolerations']]}")
        for ev in ctx.events_with_reason("NotTriggerScaleUp", "TriggeredScaleUp", "FailedScaleUp")[-2:]:
            evidence.append(format_event(ev))
            if ev.get("reason") == "NotTriggerScaleUp":
                recs.append("Cluster autoscaler will not add a node: no node group can satisfy the pod "
                            "(max size reached or constraints match no group).")
        root = ("The scheduler cannot place the pod: " + "; ".join(causes) + ".") if causes else \
            "The scheduler cannot place the pod on any node (see scheduler message)."
        return [self.finding(
            ctx, title="FailedScheduling", severity=Severity.HIGH, root_cause=root, evidence=evidence,
            confidence=92 if causes else 70, recommendations=recs or ["Review the scheduler message in the pod events."],
            commands=[describe_cmd(ctx), events_cmd(ctx),
                      f"{ctx.cmd} get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints,"
                      "CPU:.status.allocatable.cpu,MEM:.status.allocatable.memory",
                      f"{ctx.cmd} describe nodes | grep -A8 'Allocated resources'",
                      f"{ctx.cmd} get pvc -n {ctx.namespace}"])]

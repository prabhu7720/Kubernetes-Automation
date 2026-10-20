"""Node health: NotReady, pressure conditions, and pod evictions/preemption."""
from __future__ import annotations

import re
from typing import List

from core.k8s_utils import conditions_map, dig, format_event, node_pressures, node_ready
from core.models import ResourceRef, Scope, Severity

from .base import Rule

PRESSURE_GUIDE = {
    "MemoryPressure": ("available memory on the node is below the kubelet eviction threshold",
                       ["Find the top memory consumers on the node: kubectl top pods -A --sort-by=memory "
                        "(filter by node) and right-size their requests/limits.",
                        "Ensure every pod sets memory requests so the scheduler does not overpack the node."]),
    "DiskPressure": ("node filesystem / imagefs free space or inodes are below the eviction threshold",
                     ["Prune unused images (crictl rmi --prune) and check /var/lib/containerd and /var/log usage.",
                      "Set ephemeral-storage requests/limits and cap emptyDir sizeLimit; check container log rotation."]),
    "PIDPressure": ("the node is running out of process IDs",
                    ["Find pods spawning many processes/threads; set podPidsLimit in the kubelet config."]),
    "NetworkUnavailable": ("the node network/route is not configured (CNI or cloud routes)",
                           ["Check the CNI DaemonSet pod on the node and cloud route tables."]),
}


def _node_and_ref(ctx):
    node = getattr(ctx, "node", None)
    if not node:
        return None, None
    return node, ResourceRef("Node", dig(node, "metadata", "name"))


class NodeNotReadyRule(Rule):
    id = "K8S-NODE-001"
    name = "Node NotReady"
    category = "node"
    scopes = (Scope.POD, Scope.NODE)

    def evaluate(self, ctx):
        node, ref = _node_and_ref(ctx)
        if not node or node_ready(node) is not False:   # Ready=False or Ready=Unknown only
            return []
        cond = conditions_map(node).get("Ready") or {}
        name = ref.name
        reason, message = cond.get("reason", ""), cond.get("message", "")
        if cond.get("status") == "Unknown" or "stopped posting node status" in message.lower():
            root = ("The kubelet stopped reporting to the API server: the node is down/unreachable, the kubelet "
                    "crashed, or there is a network partition between node and control plane.")
            conf = 88
        elif re.search(r"container runtime (is down|not ready)|runtime network not ready", message, re.I):
            root, conf = "The container runtime (containerd/CRI-O) on the node is down or not ready.", 90
        elif re.search(r"PLEG is not healthy", message, re.I):
            root, conf = ("PLEG is unhealthy: the kubelet cannot relist containers (runtime overloaded, too many "
                          "containers, or disk I/O stalls).", 88)
        elif re.search(r"cni|network plugin", message, re.I):
            root, conf = "The CNI network plugin on the node is not initialized.", 90
        elif re.search(r"x509|certificate", message, re.I):
            root, conf = "The kubelet's client/serving certificate is invalid or expired.", 88
        else:
            root, conf = f"Node {name} is NotReady ({reason}).", 75
        evidence = [f"Node: {name}", f"Ready={cond.get('status')} reason={reason}", f"Message: {message}",
                    f"Last heartbeat: {cond.get('lastHeartbeatTime')}  transition: {cond.get('lastTransitionTime')}"]
        taints = [t.get("key") for t in dig(node, "spec", "taints") or []]
        if taints:
            evidence.append(f"Taints: {', '.join(taints)}")
        evidence += [format_event(e) for e in ctx.events if e.get("reason") in
                     ("NodeNotReady", "Rebooted", "NodeHasInsufficientMemory", "ContainerGCFailed", "KubeletIsDown")][-3:]
        if ctx.scope == Scope.POD:
            root = f"The pod runs on node {name} which is NotReady. " + root
        return [self.finding(
            ctx, resource=ref, title="Node NotReady",
            severity=Severity.CRITICAL if ctx.scope == Scope.NODE else Severity.HIGH,
            root_cause=root, evidence=evidence, confidence=conf, correlation_key=f"node-notready:{name}",
            recommendations=[
                "SSH/SSM to the node: systemctl status kubelet containerd; journalctl -u kubelet --since '-30min'.",
                "Check the cloud instance status checks / hypervisor events.",
                "If unrecoverable, cordon and drain the node and let the node group replace it.",
                "Pods on a NotReady node are evicted after the tolerationSeconds (default 300s).",
            ],
            commands=[f"{ctx.cmd} describe node {name}", f"{ctx.cmd} get node {name} -o wide",
                      f"{ctx.cmd} get pods -A -o wide --field-selector spec.nodeName={name}",
                      f"{ctx.cmd} get events -A --field-selector involvedObject.kind=Node,involvedObject.name={name}"])]


class NodePressureRule(Rule):
    id = "K8S-NODE-002"
    name = "Node pressure condition"
    category = "node"
    scopes = (Scope.POD, Scope.NODE)

    def evaluate(self, ctx):
        node, ref = _node_and_ref(ctx)
        if not node:
            return []
        findings = []
        conds = conditions_map(node)
        for ptype in node_pressures(node):
            cond = conds.get(ptype) or {}
            explanation, recs = PRESSURE_GUIDE[ptype]
            evidence = [f"Node {ref.name}: {ptype}=True ({cond.get('reason')})", f"Message: {cond.get('message')}",
                        f"Since: {cond.get('lastTransitionTime')}"]
            evidence += [format_event(e) for e in ctx.events if e.get("reason") in
                         ("EvictionThresholdMet", "FreeDiskSpaceFailed", "ImageGCFailed", "SystemOOM")][-3:]
            # At pod scope node pressure is a contributing factor unless the pod was evicted.
            pod_scope = ctx.scope == Scope.POD
            evicted = pod_scope and ctx.status.get("reason") == "Evicted"
            findings.append(self.finding(
                ctx, resource=ref, title=f"Node {ptype}",
                severity=Severity.HIGH if (not pod_scope or evicted) else Severity.MEDIUM,
                root_cause=(f"Node {ref.name} reports {ptype}: {explanation}. The kubelet taints the node and evicts pods."
                            + (" This pod runs on that node, so it is exposed to evictions and resource starvation."
                               if pod_scope else "")),
                evidence=evidence, confidence=92 if (not pod_scope or evicted) else 75,
                recommendations=recs, correlation_key=f"node-{ptype}:{ref.name}",
                commands=[f"{ctx.cmd} describe node {ref.name}", f"{ctx.cmd} top node {ref.name}",
                          f"{ctx.cmd} get pods -A -o wide --field-selector spec.nodeName={ref.name}"]))
        return findings


class EvictionRule(Rule):
    id = "K8S-NODE-003"
    name = "Pod evicted / preempted"
    category = "node"
    scopes = (Scope.POD,)

    def evaluate(self, ctx):
        status = ctx.status
        disruption = conditions_map(ctx.pod).get("DisruptionTarget") or {}
        if status.get("reason") != "Evicted" and disruption.get("status") != "True":
            return []
        message = status.get("message") or disruption.get("message") or ""
        resource = re.search(r"low on resource: ([\w-]+)", message)
        evidence = [f"Pod phase: {ctx.phase} reason: {status.get('reason') or disruption.get('reason')}",
                    f"Message: {message}", f"Node: {ctx.node_name}"]
        if resource:
            res = resource.group(1)
            root = (f"The kubelet evicted the pod because node {ctx.node_name} ran low on {res}. Pods using more "
                    f"{res} than they request are evicted first.")
            usage = re.findall(r"Container (\S+) was using (\S+), (?:request|which exceeds its request) (?:is )?(\S+)", message)
            for c, used, req in usage:
                evidence.append(f"Container {c}: used {used}, request {req}")
            recs = [f"Set {res} requests close to real usage (and limits) so the pod is not first in line for eviction.",
                    "Fix the node pressure source (see node findings) and consider a PriorityClass for critical pods."]
            if res == "ephemeral-storage":
                recs.insert(0, "Set ephemeral-storage requests/limits, cap emptyDir sizeLimit and reduce log volume.")
            conf = 95
        elif disruption.get("reason") == "PreemptionByScheduler":
            root, conf = "The pod was preempted by the scheduler to make room for a higher-priority pod.", 92
            recs = ["Assign an appropriate PriorityClass or add capacity."]
        elif disruption.get("reason") == "DeletionByTaintManager":
            root, conf = "The pod was evicted by a NoExecute taint on its node (node NotReady/unreachable).", 90
            recs = ["Investigate the node condition; adjust tolerationSeconds if appropriate."]
        else:
            root, conf = f"The pod was evicted: {message}", 80
            recs = ["Review node conditions and the eviction message."]
        recs.append(f"Clean up evicted pods: {ctx.cmd} delete pod -n {ctx.namespace} --field-selector=status.phase=Failed")
        return [self.finding(
            ctx, title="Pod evicted", severity=Severity.HIGH, root_cause=root, evidence=evidence, confidence=conf,
            recommendations=recs,
            commands=[f"{ctx.cmd} describe pod {ctx.name} -n {ctx.namespace}",
                      f"{ctx.cmd} describe node {ctx.node_name}" if ctx.node_name else "",
                      f"{ctx.cmd} get pods -A --field-selector=status.phase=Failed | grep Evicted"])]

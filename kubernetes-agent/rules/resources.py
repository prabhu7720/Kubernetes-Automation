"""Resource exhaustion: usage near limits, node overcommit, missing requests, quota exhaustion."""
from __future__ import annotations

import re
from typing import List

from core.k8s_utils import container_resources, dig, format_event, node_pressures
from core.models import ResourceRef, Scope, Severity
from core.quantity import format_bytes, format_cpu, parse_cpu, parse_memory, parse_quantity, pct

from .base import Rule


class ResourceExhaustionRule(Rule):
    id = "K8S-RES-001"
    name = "Resource exhaustion"
    category = "resources"
    scopes = (Scope.POD,)

    def evaluate(self, ctx):
        findings = []
        mem_warn = int(self.setting("memory_usage_warn_pct", 90))
        cpu_warn = int(self.setting("cpu_usage_warn_pct", 90))
        node_warn = int(self.setting("node_allocation_warn_pct", 90))
        troubled = ctx.total_restarts() > 0 or not ctx.is_ready() or bool(node_pressures(ctx.node))

        # 1. live usage vs limits (metrics-server)
        for c in ctx.containers(include_init=False):
            cname = c.get("name")
            usage = (ctx.metrics or {}).get(cname)
            if not usage:
                continue
            limits = container_resources(c)["limits"]
            mem_limit, cpu_limit = parse_memory(limits.get("memory")), parse_cpu(limits.get("cpu"))
            mem_pct, cpu_pct = pct(usage["memory_bytes"], mem_limit), pct(usage["cpu_m"], cpu_limit)
            if mem_pct is not None and mem_pct >= mem_warn:
                findings.append(self.finding(
                    ctx, title="Memory usage near limit", severity=Severity.MEDIUM, container=cname,
                    root_cause=f"Container '{cname}' uses {mem_pct}% of its memory limit; it is at imminent risk of OOMKill.",
                    evidence=[f"Memory usage: {format_bytes(usage['memory_bytes'])} / limit {limits.get('memory')}"],
                    confidence=88, correlation_key=f"memory:{ctx.namespace}/{ctx.name}/{cname}",
                    recommendations=["Raise the memory limit or reduce memory footprint; check for leaks."],
                    commands=[f"{ctx.cmd} top pod {ctx.name} -n {ctx.namespace} --containers"]))
            if cpu_pct is not None and cpu_pct >= cpu_warn:
                findings.append(self.finding(
                    ctx, title="CPU at limit (throttling)", severity=Severity.MEDIUM, container=cname,
                    root_cause=f"Container '{cname}' uses {cpu_pct}% of its CPU limit; CFS throttling is likely, which "
                               "slows requests and can make probes time out.",
                    evidence=[f"CPU usage: {format_cpu(usage['cpu_m'])} / limit {limits.get('cpu')}"], confidence=72,
                    recommendations=["Raise or remove the CPU limit (keep requests), and verify with "
                                     "container_cpu_cfs_throttled_periods_total."],
                    commands=[f"{ctx.cmd} top pod {ctx.name} -n {ctx.namespace} --containers"]))

        # 2. BestEffort / missing requests
        missing = [c.get("name") for c in ctx.containers(include_init=False)
                   if not container_resources(c)["requests"] and not container_resources(c)["limits"]]
        if missing:
            findings.append(self.finding(
                ctx, title="No resource requests/limits", severity=Severity.MEDIUM if troubled else Severity.LOW,
                root_cause=f"Container(s) {', '.join(missing)} define no requests or limits (QoS "
                           f"{ctx.status.get('qosClass', 'BestEffort')}): the scheduler cannot place them correctly and "
                           "they are the first to be evicted / OOM-killed under node pressure.",
                evidence=[f"Container {m}: requests=none limits=none" for m in missing], confidence=90,
                recommendations=["Set CPU/memory requests from observed usage and a memory limit.",
                                 "Enforce defaults with a LimitRange in the namespace."],
                commands=[f"{ctx.cmd} get limitrange -n {ctx.namespace}"]))

        # 3. node saturation (only when the pod is actually struggling)
        alloc = ctx.node_allocation
        if alloc and troubled and alloc.get("memory_allocatable"):
            mem_req_pct = pct(alloc["memory_requests"], alloc["memory_allocatable"])
            mem_lim_pct = pct(alloc["memory_limits"], alloc["memory_allocatable"])
            cpu_req_pct = pct(alloc["cpu_requests_m"], alloc["cpu_allocatable_m"])
            evidence = [f"Node {ctx.node_name}: {alloc['pods']}/{alloc['pods_allocatable']} pods",
                        f"Memory requests {format_bytes(alloc['memory_requests'])} ({mem_req_pct}%), limits "
                        f"{format_bytes(alloc['memory_limits'])} ({mem_lim_pct}%) of {format_bytes(alloc['memory_allocatable'])}",
                        f"CPU requests {format_cpu(alloc['cpu_requests_m'])} ({cpu_req_pct}%) of {format_cpu(alloc['cpu_allocatable_m'])}"]
            if (mem_lim_pct or 0) >= 150 or (mem_req_pct or 0) >= node_warn or (cpu_req_pct or 0) >= node_warn:
                findings.append(self.finding(
                    ctx, title="Node resources saturated / overcommitted", severity=Severity.MEDIUM,
                    resource=ResourceRef("Node", ctx.node_name),
                    root_cause=f"Node {ctx.node_name} is heavily committed; memory limits overcommit raises the risk of "
                               "node-level OOM and evictions affecting this pod.",
                    evidence=evidence, confidence=70,
                    recommendations=["Spread the workload (topologySpreadConstraints / anti-affinity) or add nodes.",
                                     "Reduce memory limit overcommit for pods on this node."],
                    commands=[f"{ctx.cmd} describe node {ctx.node_name} | grep -A12 'Allocated resources'"]))
        return findings


class QuotaRule(Rule):
    id = "K8S-RES-002"
    name = "ResourceQuota / LimitRange exhaustion"
    category = "resources"
    scopes = (Scope.DEPLOYMENT, Scope.NAMESPACE)

    def evaluate(self, ctx):
        findings = []
        ns = ctx.namespace
        events = ctx.events_matching(r"exceeded quota|must specify (limits|requests)|forbidden: (maximum|minimum)",
                                     reasons=("FailedCreate",))
        if events:
            msg = events[-1].get("message") or ""
            quota = re.search(r"exceeded quota: ([\w.-]+)", msg)
            if quota:
                root = (f"Pod creation is rejected because ResourceQuota '{quota.group(1)}' in namespace '{ns}' is "
                        "exhausted; new replicas cannot be created.")
                key = f"quota:{ns}/{quota.group(1)}"
            elif "must specify" in msg:
                root = ("Pod creation is rejected: a ResourceQuota requires requests/limits but the pod template "
                        "does not set them.")
                key = None
            else:
                root = "Pod creation is rejected by a LimitRange (container requests/limits outside the allowed range)."
                key = None
            findings.append(self.finding(
                ctx, title="Pod creation blocked by quota/LimitRange", severity=Severity.HIGH, root_cause=root,
                evidence=[format_event(e) for e in events[-3:]], confidence=96, correlation_key=key,
                recommendations=["Increase the quota, reduce requested resources, or scale down other workloads.",
                                 "Set requests/limits in the pod template (or a LimitRange default)."],
                commands=[f"{ctx.cmd} describe resourcequota -n {ns}", f"{ctx.cmd} describe limitrange -n {ns}"]))
        warn = int(self.setting("quota_warn_pct", 90))
        for q in getattr(ctx, "quotas", []) or []:
            qname = dig(q, "metadata", "name")
            hard, used = dig(q, "status", "hard") or {}, dig(q, "status", "used") or {}
            for res, hval in hard.items():
                parser = parse_cpu if "cpu" in res else parse_quantity
                h, u = parser(hval), parser(used.get(res, "0"))
                p = pct(u, h)
                if p is None or p < warn:
                    continue
                findings.append(self.finding(
                    ctx, resource=ResourceRef("ResourceQuota", qname, ns),
                    title="Quota nearly exhausted" if p < 100 else "Quota exhausted",
                    severity=Severity.HIGH if p >= 100 else Severity.MEDIUM,
                    root_cause=f"ResourceQuota {ns}/{qname}: {res} at {p}% ({used.get(res)}/{hval}).",
                    evidence=[f"{res}: used={used.get(res)} hard={hval}"], confidence=95,
                    correlation_key=f"quota:{ns}/{qname}",
                    recommendations=["Raise the quota or reclaim unused resources before the next rollout/scale-up."],
                    commands=[f"{ctx.cmd} describe resourcequota {qname} -n {ns}"]))
        return findings

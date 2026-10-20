"""OOMKilled detection (container memory limit or node-level OOM)."""
from __future__ import annotations

from typing import List

from core.k8s_utils import container_resources, node_pressures
from core.models import Finding, Scope, Severity
from core.quantity import format_bytes, parse_memory, pct

from ._common import describe_cmd, logs_cmd, termination
from .base import Rule

RUNTIME_OOM_PATTERNS = {
    "jvm": r"java\.lang\.OutOfMemoryError",
    "node": r"JavaScript heap out of memory|FATAL ERROR: .*Allocation failed",
    "go": r"runtime: out of memory|fatal error: runtime: cannot allocate memory",
    "python": r"\bMemoryError\b",
}


class OOMKilledRule(Rule):
    id = "K8S-OOM-001"
    name = "Container OOMKilled"
    category = "resources"
    scopes = (Scope.POD,)

    def evaluate(self, ctx) -> List[Finding]:
        findings = []
        for st in ctx.statuses():
            cname = st.get("name")
            term, when = termination(st)
            last = (st.get("lastState") or {}).get("terminated") or {}
            if term.get("reason") != "OOMKilled" and last.get("reason") == "OOMKilled":
                term, when = last, "last"
            if term.get("reason") == "OOMKilled":
                confidence = 95
            elif term.get("exitCode") == 137:
                confidence = 65   # SIGKILL without explicit OOM reason (could be grace-period kill)
            else:
                continue

            spec = ctx.spec_of(cname) or {}
            res = container_resources(spec)
            mem_limit = res["limits"].get("memory")
            mem_request = res["requests"].get("memory")
            restarts = st.get("restartCount") or 0
            evidence = [
                f"Container: {cname}",
                f"Exit Code: {term.get('exitCode')}",
                f"Termination Reason: {term.get('reason')} ({when} state)",
                f"Restart count: {restarts}",
                f"Memory limit: {mem_limit or 'NOT SET'}",
                f"Memory request: {mem_request or 'NOT SET'}",
            ]
            if term.get("finishedAt"):
                evidence.append(f"Terminated at: {term['finishedAt']}")
            usage = (ctx.metrics or {}).get(cname)
            if usage:
                limit_b = parse_memory(mem_limit)
                p = pct(usage["memory_bytes"], limit_b)
                evidence.append(f"Current memory usage: {format_bytes(usage['memory_bytes'])}"
                                + (f" ({p}% of limit)" if p is not None else ""))

            runtime = None
            for rt, rx in RUNTIME_OOM_PATTERNS.items():
                hits = ctx.search_logs([rx], containers=[cname], max_hits=1)
                if hits:
                    runtime = rt
                    evidence.append(hits[0].render())
                    break

            node_mem_pressure = "MemoryPressure" in node_pressures(ctx.node)
            if mem_limit:
                root = (f"Container '{cname}' exceeded its configured memory limit ({mem_limit}) "
                        "and was killed by the kernel OOM killer.")
            else:
                root = (f"Container '{cname}' has no memory limit and was OOM killed because the node "
                        "ran out of memory (node-level OOM).")
            if runtime:
                root += f" The {runtime.upper()} runtime also reported running out of heap."
            if node_mem_pressure:
                evidence.append(f"Node {ctx.node_name} currently reports MemoryPressure=True")

            recs = [
                f"Increase the memory limit for container '{cname}' (currently {mem_limit or 'unset'}); size it "
                "from observed peak usage plus 20-30% headroom.",
                "Check for a memory leak: compare memory growth over time "
                "(container_memory_working_set_bytes) and capture a heap profile/dump.",
                "Monitor usage after the change (kubectl top / Prometheus) and consider VPA recommendations.",
            ]
            if runtime == "jvm":
                recs.append("Align JVM heap with the container limit: -XX:MaxRAMPercentage=75 (avoid fixed -Xmx above the limit).")
            elif runtime == "node":
                recs.append("Set --max-old-space-size to ~75% of the container memory limit.")
            elif runtime == "go":
                recs.append("Set GOMEMLIMIT to ~90% of the container memory limit.")
            if not mem_request or mem_request != mem_limit:
                recs.append("For critical workloads set memory request == limit (Guaranteed QoS) to reduce eviction risk.")
            if not mem_limit:
                recs.append("Define memory requests/limits so the scheduler can place the pod correctly.")

            findings.append(self.finding(
                ctx, title="Container OOMKilled", severity=Severity.HIGH,
                root_cause=root, evidence=evidence, confidence=confidence, recommendations=recs,
                container=cname, correlation_key=f"termination:{ctx.namespace}/{ctx.name}/{cname}",
                commands=[
                    f"{ctx.cmd} top pod {ctx.name} -n {ctx.namespace} --containers",
                    describe_cmd(ctx),
                    logs_cmd(ctx, cname, previous=True),
                    f"{ctx.cmd} get pod {ctx.name} -n {ctx.namespace} -o jsonpath='{{.status.containerStatuses[*].lastState}}'",
                    f"{ctx.cmd} describe node {ctx.node_name}" if ctx.node_name else "",
                ]))
        return findings

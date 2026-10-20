"""CrashLoopBackOff, frequent restarts and failed (non-restarting) containers."""
from __future__ import annotations

import re
from typing import List

from core.models import Finding, Scope, Severity

from ._common import (FATAL_LOG_PATTERNS, describe_cmd, exit_code_meaning, liveness_kill_events, logs_cmd,
                      run_duration_seconds, termination, waiting)
from .base import Rule

_CODE_RECS = {
    0: "The main process exits by itself: ensure it runs in the foreground (no daemonizing) and does not finish "
       "immediately; for batch work use a Job instead of a Deployment.",
    1: "Read the previous container logs for the stack trace / error and fix the application or its configuration.",
    126: "Make the entrypoint executable (chmod +x in the Dockerfile) and verify file ownership vs runAsUser.",
    127: "Fix command/args/entrypoint - the binary does not exist in the image (check image tag & PATH).",
    134: "The process aborted - inspect logs/core dump for assertion failures or native library errors.",
    137: "Process was SIGKILLed - check for OOM, failing liveness probes, or a slow shutdown exceeding terminationGracePeriodSeconds.",
    139: "Segmentation fault - check native dependencies/base image compatibility and CPU architecture.",
    143: "Process received SIGTERM - correlate with liveness probe failures, evictions, or rollouts.",
}

# Log signatures owned by the network / certificate / RBAC rules
DEPENDENCY_PATTERNS = [
    r"connection refused|ECONNREFUSED", r"no such host|name resolution|ENOTFOUND|UnknownHostException",
    r"x509:|certificate verify failed|PKIX", r'is forbidden: User "', r"i/o timeout|ETIMEDOUT",
]

_SPECIAL_LOG_CAUSES = [
    (re.compile(r"exec format error", re.I),
     "The image was built for a different CPU architecture than the node (e.g. arm64 image on amd64 node).", 95,
     "Build a multi-arch image (docker buildx --platform linux/amd64,linux/arm64) or pin nodeSelector kubernetes.io/arch."),
    (re.compile(r"address already in use", re.I),
     "The application cannot bind its listening port because it is already in use (port conflict with a sidecar or hostNetwork).", 85,
     "Change the listening port or remove the conflicting sidecar / hostNetwork usage."),
    (re.compile(r"permission denied", re.I),
     "The process hit a filesystem permission error (securityContext runAsUser/fsGroup vs file ownership, read-only root filesystem).", 75,
     "Align securityContext (runAsUser, fsGroup) with file ownership, or mount a writable emptyDir for paths the app writes to."),
    (re.compile(r"APPLICATION FAILED TO START|Error creating bean|Could not resolve placeholder", re.I),
     "Application startup failed due to configuration (missing/invalid properties or dependencies).", 85,
     "Check the referenced configuration properties, environment variables and mounted config files."),
]


def _analyze_exit(ctx, rule: Rule, cname: str):
    """Shared exit analysis: returns (root_cause, confidence, evidence, recs)."""
    st = ctx.status_of(cname) or {}
    term, _ = termination(st)
    code = term.get("exitCode")
    evidence = [f"Last termination reason: {term.get('reason') or 'n/a'}", f"Exit Code: {code}"]
    duration = run_duration_seconds(term)
    if duration is not None:
        evidence.append(f"Container ran for {int(duration)}s before exiting")
    recs = [_CODE_RECS.get(code, "Inspect the previous container logs to find why the process exits.")]
    confidence = 70

    hits = ctx.search_logs(FATAL_LOG_PATTERNS, containers=[cname], sources=("previous", "current"),
                           max_hits=rule.max_evidence)
    root = f"Container '{cname}' repeatedly exits with code {code} ({exit_code_meaning(code)})."
    for rx, cause, conf, rec in _SPECIAL_LOG_CAUSES:
        if any(rx.search(h.line) for h in hits):
            root = cause
            confidence = conf
            recs.insert(0, rec)
            break
    else:
        if hits:
            root += " The container logs show the application failing - see the log evidence."
            confidence = 85
        elif code in (126, 127):
            confidence = 85
    if hits:
        evidence.extend(h.render() for h in hits)
    else:
        tail = ctx.last_log_lines(cname, n=3, previous=True) or ctx.last_log_lines(cname, n=3, previous=False)
        if tail:
            evidence.extend(f"[{cname} last log line] {l.strip()}" for l in tail)
        else:
            evidence.append("No previous log output: the process failed before logging "
                            "(check command/args, entrypoint, mounted files).")
    if duration is not None and duration < 10:
        evidence.append("Very short run time suggests a startup failure (config, dependency, command).")
    return root, confidence, evidence, recs


class CrashLoopBackOffRule(Rule):
    id = "K8S-CRASH-001"
    name = "CrashLoopBackOff"
    category = "workload"
    scopes = (Scope.POD,)

    def evaluate(self, ctx) -> List[Finding]:
        findings = []
        for st in ctx.statuses():
            reason, message = waiting(st)
            if reason != "CrashLoopBackOff":
                continue
            cname = st.get("name")
            term, _ = termination(st)
            restarts = st.get("restartCount") or 0
            evidence = [f"Container: {cname}", "State: Waiting (CrashLoopBackOff)", f"Restart count: {restarts}"]
            if message:
                evidence.append(f"Back-off: {message}")
            is_symptom = False
            kills = liveness_kill_events(ctx, cname)
            if term.get("reason") == "OOMKilled":
                root = (f"CrashLoopBackOff of '{cname}' is a symptom: the container is repeatedly OOMKilled "
                        "(see the OOMKilled finding).")
                confidence, recs, is_symptom = 90, ["Resolve the OOMKilled finding (memory limit / leak)."], True
                evidence += [f"Last termination reason: OOMKilled", f"Exit Code: {term.get('exitCode')}"]
            elif kills:
                root = (f"CrashLoopBackOff of '{cname}' is driven by liveness probe failures: the kubelet keeps "
                        "killing the container (see the liveness probe finding).")
                confidence, recs, is_symptom = 85, ["Resolve the liveness probe failure finding."], True
                evidence.append(f"Liveness kill events: {sum(int(e.get('count') or 1) for e in kills)}")
            else:
                root, confidence, extra, recs = _analyze_exit(ctx, self, cname)
                evidence += extra
                if ctx.search_logs(DEPENDENCY_PATTERNS, containers=[cname], max_hits=1):
                    is_symptom = True
                    root += (" The process aborts because a startup dependency fails (network/DNS/TLS/RBAC) - "
                             "the dependency findings for this pod carry the actual root cause.")
                    recs.insert(0, "Fix the dependency failure reported in the related network/DNS/TLS/RBAC findings.")
                else:
                    recs.append("Check related findings (DNS, connection refused, missing config) - "
                                "dependency failures at startup commonly cause crash loops.")
            if cname in ctx.init_container_names():
                root = f"[init container] {root} The pod cannot start until this init container succeeds."
            findings.append(self.finding(
                ctx, title="CrashLoopBackOff", severity=Severity.HIGH, root_cause=root,
                evidence=evidence, confidence=confidence, recommendations=recs, container=cname,
                is_symptom=is_symptom,
                commands=[logs_cmd(ctx, cname, previous=True), logs_cmd(ctx, cname), describe_cmd(ctx),
                          f"{ctx.cmd} get pod {ctx.name} -n {ctx.namespace} -o yaml"]))
        return findings


class FrequentRestartsRule(Rule):
    id = "K8S-CRASH-002"
    name = "Frequent container restarts"
    category = "workload"
    scopes = (Scope.POD,)

    def evaluate(self, ctx) -> List[Finding]:
        threshold = int(self.setting("restart_threshold", 3))
        findings = []
        for st in ctx.statuses():
            cname = st.get("name")
            restarts = st.get("restartCount") or 0
            reason, _ = waiting(st)
            term, _ = termination(st)
            if restarts < threshold or reason == "CrashLoopBackOff" or term.get("reason") == "OOMKilled":
                continue
            kills = liveness_kill_events(ctx, cname)
            if kills:
                root = f"Container '{cname}' restarts because its liveness probe fails (see liveness finding)."
                findings.append(self.finding(
                    ctx, title="Frequent container restarts", severity=Severity.MEDIUM, root_cause=root,
                    evidence=[f"Container: {cname}", f"Restart count: {restarts}",
                              f"Liveness kill events: {len(kills)}"],
                    confidence=85, container=cname, is_symptom=True,
                    recommendations=["Resolve the liveness probe failure finding."],
                    commands=[describe_cmd(ctx)]))
                continue
            root, confidence, extra, recs = _analyze_exit(ctx, self, cname)
            findings.append(self.finding(
                ctx, title="Frequent container restarts", severity=Severity.MEDIUM,
                root_cause=f"Container '{cname}' restarted {restarts} times. {root}",
                evidence=[f"Container: {cname}", f"Restart count: {restarts}"] + extra,
                confidence=max(50, confidence - 10), recommendations=recs, container=cname,
                commands=[logs_cmd(ctx, cname, previous=True), describe_cmd(ctx)]))
        return findings


class ContainerFailedRule(Rule):
    """Containers that terminated with an error and are not restarted (Jobs, restartPolicy Never/OnFailure)."""

    id = "K8S-CRASH-003"
    name = "Container terminated with error"
    category = "workload"
    scopes = (Scope.POD,)

    def evaluate(self, ctx) -> List[Finding]:
        if ctx.status.get("reason") == "Evicted":
            return []
        findings = []
        for st in ctx.statuses():
            term = (st.get("state") or {}).get("terminated") or {}
            if not term or term.get("exitCode", 0) == 0 or term.get("reason") in ("OOMKilled", "Completed"):
                continue
            cname = st.get("name")
            root, confidence, extra, recs = _analyze_exit(ctx, self, cname)
            sev = Severity.HIGH if ctx.phase == "Failed" else Severity.MEDIUM
            findings.append(self.finding(
                ctx, title="Container terminated with error", severity=sev, root_cause=root,
                evidence=[f"Container: {cname}", f"Pod phase: {ctx.phase}",
                          f"restartPolicy: {ctx.spec.get('restartPolicy', 'Always')}"] + extra,
                confidence=confidence, recommendations=recs, container=cname,
                correlation_key=f"termination:{ctx.namespace}/{ctx.name}/{cname}",
                commands=[logs_cmd(ctx, cname), describe_cmd(ctx)]))
        return findings

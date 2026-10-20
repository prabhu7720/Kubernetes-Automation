"""Readiness / liveness / startup probe failure analysis."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core.k8s_utils import container_from_event, event_count, event_time
from core.models import Finding, Scope, Severity

from ._common import describe_cmd, events_cmd, liveness_kill_events, logs_cmd
from .base import Rule


def describe_probe(probe: Optional[Dict[str, Any]]) -> str:
    if not probe:
        return "not configured"
    if "httpGet" in probe:
        h = probe["httpGet"]
        handler = f"httpGet {h.get('scheme', 'HTTP').lower()}://:{h.get('port')}{h.get('path', '/')}"
    elif "tcpSocket" in probe:
        handler = f"tcpSocket :{probe['tcpSocket'].get('port')}"
    elif "grpc" in probe:
        handler = f"grpc :{probe['grpc'].get('port')}"
    elif "exec" in probe:
        handler = "exec " + " ".join(probe["exec"].get("command") or [])[:120]
    else:
        handler = "unknown handler"
    return (f"{handler} initialDelaySeconds={probe.get('initialDelaySeconds', 0)} "
            f"periodSeconds={probe.get('periodSeconds', 10)} timeoutSeconds={probe.get('timeoutSeconds', 1)} "
            f"failureThreshold={probe.get('failureThreshold', 3)}")


def probe_port(probe: Dict[str, Any]):
    for key in ("httpGet", "tcpSocket", "grpc"):
        if key in probe:
            return probe[key].get("port")
    return None


def port_declared(container: Dict[str, Any], probe: Dict[str, Any]) -> Optional[bool]:
    port = probe_port(probe or {})
    if port is None:
        return None
    ports = container.get("ports") or []
    if isinstance(port, str) and not port.isdigit():
        return any(p.get("name") == port for p in ports)      # named port must exist
    if not ports:
        return None  # declaring ports is optional; cannot judge
    return any(str(p.get("containerPort")) == str(port) for p in ports)


def classify(message: str, probe: Dict[str, Any], probe_type: str) -> Tuple[str, int, List[str]]:
    msg = message or ""
    timeout = probe.get("timeoutSeconds", 1)
    delay = probe.get("initialDelaySeconds", 0)
    m = re.search(r"statuscode:\s*(\d+)", msg, re.I)
    if m:
        code = int(m.group(1))
        if code == 404:
            return ("The probe path returns HTTP 404: the configured path is wrong or the health endpoint is not registered.",
                    90, ["Fix httpGet.path to the application's real health endpoint (e.g. /healthz, /actuator/health)."])
        if code in (401, 403):
            return (f"The health endpoint requires authentication (HTTP {code}).", 88,
                    ["Exempt the health endpoint from authentication / authorization middleware."])
        if code >= 500:
            return (f"The application reports itself unhealthy (HTTP {code}); typically a failing dependency check "
                    "(database, cache, downstream API) or an internal error.", 80,
                    ["Check application logs around the failure time for the failing dependency.",
                     "Keep liveness checks shallow (process health only); put dependency checks in readiness."])
        return (f"The health endpoint returned unexpected HTTP {code}.", 70, ["Verify the health endpoint behaviour."])
    if re.search(r"server gave HTTP response to HTTPS client|first record does not look like a TLS handshake", msg, re.I):
        return ("Probe scheme mismatch: probe uses HTTPS against an HTTP port (or vice versa).", 92,
                ["Set httpGet.scheme to match what the application serves on that port."])
    if re.search(r"connection refused", msg, re.I):
        return ("Nothing is listening on the probe port when the probe runs: the application has not started yet "
                f"(initialDelaySeconds={delay} may be too short), listens on a different port, or binds to 127.0.0.1 "
                "instead of 0.0.0.0.", 80,
                ["Confirm the app listens on the probe port on 0.0.0.0 (kubectl exec ... -- netstat -tlnp / ss -tlnp).",
                 "For slow-starting apps add a startupProbe instead of a long initialDelaySeconds."])
    if re.search(r"timeout|deadline exceeded|Client\.Timeout|timed out", msg, re.I):
        return (f"The health endpoint responds slower than timeoutSeconds={timeout}s (CPU throttling, GC pauses, "
                "thread-pool exhaustion or a health handler doing heavy work).", 75,
                [f"Increase timeoutSeconds (currently {timeout}s) and check CPU throttling / limits.",
                 "Make the health handler lightweight and non-blocking."])
    if re.search(r"connection reset|EOF", msg, re.I):
        return ("The application closes the probe connection (crash during request, TLS mismatch, or overload).", 65,
                ["Check application logs at the time of the failures."])
    if re.search(r"OCI runtime exec failed|executable file not found|no such file", msg, re.I):
        return ("The exec probe command does not exist in the container image.", 90,
                ["Fix exec.command or install the required tool (e.g. curl/grpc_health_probe) in the image."])
    if "exec" in probe:
        return ("The exec probe command returned a non-zero exit code.", 70,
                ["Run the probe command manually with kubectl exec to see its output."])
    return (f"{probe_type} probe is failing; see the probe failure message in the evidence.", 60, [])


class _ProbeFailureRule(Rule):
    probe_type = ""
    spec_key = ""
    category = "probes"
    scopes = (Scope.POD,)

    def _failures(self, ctx) -> Dict[str, List[Dict[str, Any]]]:
        prefix = f"{self.probe_type} probe"
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for ev in ctx.events_with_reason("Unhealthy"):
            msg = ev.get("message") or ""
            if not (msg.startswith(f"{prefix} failed") or msg.startswith(f"{prefix} errored")):
                continue
            cname = container_from_event(ev)
            if not cname:
                cname = next((c.get("name") for c in ctx.containers() if c.get(self.spec_key)), "?")
            groups.setdefault(cname, []).append(ev)
        return groups

    def severity_for(self, ctx, status: Dict[str, Any]) -> Severity:
        return Severity.HIGH

    def evaluate(self, ctx) -> List[Finding]:
        findings = []
        for cname, events in self._failures(ctx).items():
            spec = ctx.spec_of(cname) or {}
            probe = spec.get(self.spec_key) or {}
            status = ctx.status_of(cname) or {}
            latest = events[-1]
            message = latest.get("message") or ""
            root, conf, recs = classify(message, probe, self.probe_type)
            evidence = [
                f"Container: {cname}",
                f"{self.probe_type} probe: {describe_probe(probe)}",
                f"Probe failures: {sum(event_count(e) for e in events)} (last at {event_time(latest) or '?'})",
                f"Last failure: {' '.join(message.split())[:300]}",
                f"Container ready: {status.get('ready')}  restarts: {status.get('restartCount', 0)}",
            ]
            declared = port_declared(spec, probe)
            if declared is False:
                evidence.append(f"Probe port '{probe_port(probe)}' is NOT declared in the container ports")
                root = f"The probe targets port '{probe_port(probe)}' which the container does not expose. " + root
                conf = max(conf, 88)
                recs.insert(0, "Point the probe at the port the application actually listens on.")
            recs += self.extra_recommendations(probe)
            self.extra_evidence(ctx, cname, evidence)
            findings.append(self.finding(
                ctx, title=f"{self.probe_type} probe failure", severity=self.severity_for(ctx, status),
                root_cause=root, evidence=evidence, confidence=conf, recommendations=recs, container=cname,
                commands=[describe_cmd(ctx), events_cmd(ctx), logs_cmd(ctx, cname),
                          f"{ctx.cmd} get pod {ctx.name} -n {ctx.namespace} -o jsonpath="
                          f"'{{.spec.containers[?(@.name==\"{cname}\")].{self.spec_key}}}'",
                          f"{ctx.cmd} exec -it {ctx.name} -n {ctx.namespace} -c {cname} -- "
                          f"sh -c 'wget -qO- http://127.0.0.1:{probe_port(probe) or '<port>'}"
                          f"{(probe.get('httpGet') or {}).get('path', '/')} || curl -sv "
                          f"http://127.0.0.1:{probe_port(probe) or '<port>'}{(probe.get('httpGet') or {}).get('path', '/')}'"]))
        return findings

    def extra_recommendations(self, probe: Dict[str, Any]) -> List[str]:
        return []

    def extra_evidence(self, ctx, cname: str, evidence: List[str]) -> None:
        return None


class ReadinessProbeRule(_ProbeFailureRule):
    id = "K8S-PROBE-001"
    name = "Readiness probe failure"
    probe_type = "Readiness"
    spec_key = "readinessProbe"

    def severity_for(self, ctx, status):
        if not status.get("ready"):
            return Severity.HIGH if ctx.phase == "Running" else Severity.MEDIUM
        return Severity.LOW  # recovered; historical failures only

    def extra_recommendations(self, probe):
        return ["While not ready the pod is removed from Service endpoints; verify with kubectl get endpoints."]


class LivenessProbeRule(_ProbeFailureRule):
    id = "K8S-PROBE-002"
    name = "Liveness probe failure"
    probe_type = "Liveness"
    spec_key = "livenessProbe"

    def severity_for(self, ctx, status):
        return Severity.HIGH if (status.get("restartCount") or 0) > 0 else Severity.MEDIUM

    def extra_evidence(self, ctx, cname, evidence):
        kills = liveness_kill_events(ctx, cname)
        if kills:
            evidence.append(f"Kubelet restarted the container after liveness failures {sum(event_count(e) for e in kills)} time(s)")

    def extra_recommendations(self, probe):
        return ["Liveness failures restart the container - make sure the liveness probe does not depend on "
                "external services and has a generous failureThreshold.",
                "Use a startupProbe so liveness only starts after the application finished booting."]


class StartupProbeRule(_ProbeFailureRule):
    id = "K8S-PROBE-003"
    name = "Startup probe failure"
    probe_type = "Startup"
    spec_key = "startupProbe"

    def extra_recommendations(self, probe):
        budget = probe.get("failureThreshold", 3) * probe.get("periodSeconds", 10)
        return [f"The startup budget is failureThreshold x periodSeconds = {budget}s; raise it if the app "
                "legitimately needs longer to boot."]

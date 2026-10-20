"""Network-level failures seen in logs/events: DNS, connection refused, timeouts, CNI."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from core.k8s_utils import format_event
from core.models import Finding, Scope, Severity

from ._common import describe_cmd, events_cmd, impact_severity
from .base import Rule

WELL_KNOWN_PORTS = {
    "5432": "PostgreSQL", "3306": "MySQL", "6379": "Redis", "27017": "MongoDB", "9092": "Kafka",
    "5672": "RabbitMQ", "9200": "Elasticsearch", "2181": "ZooKeeper", "11211": "Memcached",
    "1433": "SQL Server", "1521": "Oracle", "8500": "Consul", "2379": "etcd", "4317": "OTLP collector",
    "15000": "Envoy admin", "15020": "Istio sidecar", "443": "HTTPS", "80": "HTTP",
}

DNS_PATTERNS = [
    r"no such host", r"temporary failure in name resolution", r"name or service not known",
    r"could not resolve host", r"getaddrinfo (ENOTFOUND|EAI_AGAIN)", r"\bNXDOMAIN\b",
    r"UnknownHostException", r"nodename nor servname provided", r"server misbehaving",
    r"lookup \S+ on \S+:53: .*(timeout|refused|no such host)", r"failed to resolve", r"dns.*(timed out|timeout)",
    r"Name does not resolve",
]
HOST_EXTRACTORS = [
    r"lookup ([\w.-]+)", r"ENOTFOUND ([\w.-]+)", r"EAI_AGAIN ([\w.-]+)", r"UnknownHostException:? ([\w.-]+)",
    r"resolve host:? '?([\w.-]+)", r"host '?([\w.-]+)'?: (?:Name|Temporary)", r"failed to resolve '?([\w.-]+)",
]

REFUSED_PATTERNS = [r"connection refused", r"ECONNREFUSED", r"actively refused", r"could not connect to server"]
TARGET_EXTRACTORS = [
    r"dial tcp \[?([\w.:-]+?)\]?:(\d+)", r"ECONNREFUSED \[?([\w.:-]+?)\]?:(\d+)",
    r"connect(?:ing)? to (?:server at )?\"?([\w.-]+)\"? \(?[\d.]*\)?,? (?:port|:)\s?(\d+)",
    r"([\w.-]+):(\d+).*[Cc]onnection refused",
]
TIMEOUT_PATTERNS = [r"i/o timeout", r"connection timed out", r"ETIMEDOUT", r"connect timeout",
                    r"context deadline exceeded", r"SocketTimeoutException", r"Connection timed out"]


def _extract(lines: List[str], extractors: List[str]) -> List[Tuple[str, ...]]:
    found = []
    for line in lines:
        for rx in extractors:
            m = re.search(rx, line, re.I)
            if m:
                found.append(m.groups())
                break
    return list(dict.fromkeys(found))


def _is_cluster_name(host: str) -> bool:
    return host.endswith(".svc") or ".svc." in host or host.endswith(".cluster.local") or "." not in host


class DNSFailureRule(Rule):
    id = "K8S-NET-001"
    name = "DNS resolution failure"
    category = "network"
    scopes = (Scope.POD,)

    def evaluate(self, ctx) -> List[Finding]:
        hits = ctx.search_logs(self.patterns("log", DNS_PATTERNS), max_hits=self.max_evidence)
        if not hits:
            return []
        lines = [h.line for h in hits]
        hosts = [g[0] for g in _extract(lines, HOST_EXTRACTORS) if g and g[0]]
        dns_server_timeout = any(re.search(r"on [\d.]+:53: .*(i/o timeout|read udp|connection refused)", l, re.I)
                                 for l in lines)
        cluster_hosts = [h for h in hosts if _is_cluster_name(h)]
        if dns_server_timeout:
            root = ("The pod cannot reach the cluster DNS service (queries to kube-dns time out/are refused): CoreDNS is "
                    "down/overloaded or a NetworkPolicy blocks egress to kube-system on port 53.")
            conf = 85
        elif cluster_hosts:
            root = (f"In-cluster name(s) {', '.join(cluster_hosts[:3])} do not resolve: the target Service does not exist, "
                    "lives in another namespace (use <svc>.<namespace>.svc.cluster.local), or is misspelled.")
            conf = 85
        elif hosts:
            root = (f"External name(s) {', '.join(hosts[:3])} do not resolve: upstream DNS/forwarders, private DNS zone "
                    "association, or egress restrictions.")
            conf = 78
        else:
            root = "The application fails DNS lookups (see log evidence)."
            conf = 70
        dns_policy = ctx.spec.get("dnsPolicy", "ClusterFirst")
        evidence = [h.render() for h in hits] + [f"dnsPolicy: {dns_policy}"]
        if ctx.spec.get("dnsConfig"):
            evidence.append(f"dnsConfig: {ctx.spec['dnsConfig']}")
        if dns_policy in ("Default", "None"):
            root += f" Note: dnsPolicy={dns_policy} bypasses cluster DNS."
        target = (cluster_hosts or hosts or ["kubernetes.default"])[0]
        return [self.finding(
            ctx, title="DNS resolution failure", severity=impact_severity(ctx, None, Severity.HIGH, Severity.MEDIUM),
            root_cause=root, evidence=evidence, confidence=conf,
            recommendations=[
                "Verify the target Service exists and has endpoints: kubectl get svc,endpoints -A | grep <name>.",
                "Check CoreDNS health and logs (kube-system, k8s-app=kube-dns).",
                "Check NetworkPolicies allow egress UDP/TCP 53 to kube-system/kube-dns.",
                "Inside the pod, inspect /etc/resolv.conf (ndots:5 can cause slow external lookups - use FQDNs with a trailing dot).",
            ],
            commands=[
                f"{ctx.cmd} run dns-debug --rm -it --restart=Never -n {ctx.namespace} --image=busybox:1.36 -- nslookup {target}",
                f"{ctx.cmd} exec {ctx.name} -n {ctx.namespace} -- cat /etc/resolv.conf",
                f"{ctx.cmd} get pods -n kube-system -l k8s-app=kube-dns -o wide",
                f"{ctx.cmd} logs -n kube-system -l k8s-app=kube-dns --tail=50",
                f"{ctx.cmd} get networkpolicy -n {ctx.namespace}",
            ])]


class ConnectionRefusedRule(Rule):
    id = "K8S-NET-002"
    name = "Connection refused"
    category = "network"
    scopes = (Scope.POD,)

    def evaluate(self, ctx) -> List[Finding]:
        hits = ctx.search_logs(self.patterns("log", REFUSED_PATTERNS), max_hits=self.max_evidence)
        if not hits:
            return []
        targets = _extract([h.line for h in hits], TARGET_EXTRACTORS)
        descr = []
        localhost = False
        for host, port in targets[:3]:
            svc = WELL_KNOWN_PORTS.get(port)
            descr.append(f"{host}:{port}" + (f" ({svc})" if svc else ""))
            if host in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
                localhost = True
        if localhost:
            root = (f"The application cannot connect to {', '.join(descr)} on localhost: a sidecar it depends on "
                    "(service-mesh proxy, cloud-sql-proxy, vault agent...) is not ready yet or not running, or the "
                    "app connects to localhost instead of a Service name.")
            conf = 82
            recs = ["Ensure the sidecar starts first (native sidecars: initContainers with restartPolicy: Always; "
                    "Istio: holdApplicationUntilProxyStarts).",
                    "If the dependency is a separate Service, use its Service DNS name instead of localhost."]
        else:
            target = ", ".join(descr) if descr else "a dependency"
            root = (f"The application's dependency {target} is refusing TCP connections: the target is down, "
                    "has no ready endpoints behind its Service, or listens on a different port.")
            conf = 80 if descr else 70
            recs = ["Check that the target Service has ready endpoints: kubectl get endpoints <svc> -n <ns>.",
                    "Verify the Service targetPort matches the container port of the backend pods.",
                    "Check the health of the dependency (database/cache/broker) itself.",
                    "Add retry with backoff at startup so transient dependency restarts do not crash the app."]
        return [self.finding(
            ctx, title="Connection refused to dependency",
            severity=impact_severity(ctx, None, Severity.HIGH, Severity.MEDIUM), root_cause=root,
            evidence=[h.render() for h in hits], confidence=conf, recommendations=recs,
            commands=[f"{ctx.cmd} get svc,endpoints -n {ctx.namespace}",
                      f"{ctx.cmd} get endpointslices -n {ctx.namespace}",
                      f"{ctx.cmd} exec -it {ctx.name} -n {ctx.namespace} -- sh -c 'nc -zv "
                      f"{targets[0][0] if targets else '<host>'} {targets[0][1] if targets else '<port>'}'",
                      f"{ctx.cmd} get networkpolicy -n {ctx.namespace}"])]


class NetworkTimeoutRule(Rule):
    id = "K8S-NET-003"
    name = "Network timeout"
    category = "network"
    scopes = (Scope.POD,)

    def evaluate(self, ctx) -> List[Finding]:
        hits = ctx.search_logs(self.patterns("log", TIMEOUT_PATTERNS), max_hits=self.max_evidence,
                               exclude=r"lookup \S+ on|probe")
        if not hits:
            return []
        targets = _extract([h.line for h in hits], TARGET_EXTRACTORS)
        descr = ", ".join(f"{h}:{p}" for h, p in targets[:3]) or "a dependency"
        return [self.finding(
            ctx, title="Network timeout to dependency", severity=impact_severity(ctx, None, Severity.MEDIUM, Severity.LOW),
            root_cause=(f"Connections to {descr} time out (packets dropped rather than refused): typically a "
                        "NetworkPolicy, security group / firewall, missing route/NAT, or an overloaded target."),
            evidence=[h.render() for h in hits], confidence=65,
            recommendations=["Review NetworkPolicies (ingress on target and egress on source).",
                             "Check cloud security groups / firewall rules and NAT for external targets.",
                             "Test connectivity from a debug pod in the same namespace."],
            commands=[f"{ctx.cmd} get networkpolicy -n {ctx.namespace} -o yaml",
                      f"{ctx.cmd} debug -it {ctx.name} -n {ctx.namespace} --image=nicolaka/netshoot --target="
                      f"{(ctx.containers(False) or [{}])[0].get('name', '<container>')}"])]


class CNIFailureRule(Rule):
    id = "K8S-NET-004"
    name = "Pod sandbox / CNI failure"
    category = "network"
    scopes = (Scope.POD,)

    def evaluate(self, ctx) -> List[Finding]:
        events = ctx.events_with_reason("FailedCreatePodSandBox", "FailedKillPodSandBox")
        events += ctx.events_matching(r"network plugin is not ready|cni plugin not initialized|failed to setup network")
        if not events:
            return []
        text = " ".join(e.get("message") or "" for e in events)
        if re.search(r"failed to assign an IP|no available IP|InsufficientFreeAddressesInSubnet|ipam|"
                     r"no IP addresses available|range is full", text, re.I):
            root, conf = ("The CNI cannot allocate a pod IP: the subnet / IP pool is exhausted (e.g. AWS VPC CNI ENI/IP limits).", 90)
            recs = ["Free IPs or enlarge the pod subnet; enable prefix delegation (AWS VPC CNI) or add secondary CIDRs.",
                    "Check max pods per node vs available ENI IPs."]
        elif re.search(r"network plugin is not ready|cni plugin not initialized|cni config uninitialized", text, re.I):
            root, conf = ("The CNI plugin is not running/initialized on the node.", 90)
            recs = ["Check the CNI DaemonSet pods (aws-node, calico-node, cilium, flannel) on the node and their logs."]
        else:
            root, conf = ("The container runtime failed to create the pod sandbox (network namespace) - see event.", 70)
            recs = ["Check kubelet/containerd logs on the node and the CNI DaemonSet health."]
        return [self.finding(
            ctx, title="Pod sandbox / CNI failure", severity=Severity.HIGH, root_cause=root,
            evidence=[format_event(e) for e in events[-3:]] + [f"Node: {ctx.node_name}"], confidence=conf,
            recommendations=recs,
            commands=[describe_cmd(ctx), events_cmd(ctx),
                      f"{ctx.cmd} get pods -n kube-system -o wide --field-selector spec.nodeName={ctx.node_name}"])]

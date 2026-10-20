"""Diagnostic contexts: everything collectors gathered about one resource.

Rules are pure functions of a context: they never call kubectl themselves.
This keeps rules fast, deterministic, and unit-testable with plain dicts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, Iterable, List, NamedTuple, Optional, Pattern, Sequence, Set, Union

from config.settings import Settings

from .k8s_utils import (all_container_statuses, all_containers, conditions_map, container_from_event, dig,
                        sort_events)
from .models import ResourceRef, Scope

PatternLike = Union[str, Pattern]


class LogHit(NamedTuple):
    container: str
    source: str  # "previous" | "current"
    line_no: int
    line: str

    def render(self) -> str:
        return f"[{self.container} {self.source} log] {self.line.strip()}"


def _compile(patterns: Iterable[PatternLike]) -> List[Pattern]:
    return [p if isinstance(p, re.Pattern) else re.compile(p, re.IGNORECASE) for p in patterns]


def _normalize(line: str) -> str:
    return re.sub(r"[0-9a-f]{8,}|\d+", "#", line.strip().lower())[:200]


@dataclass
class BaseContext:
    scope: ClassVar[Scope]
    settings: Settings = field(default_factory=Settings)
    cmd: str = "kubectl"                       # kubectl prefix for printed validation commands
    events: List[Dict[str, Any]] = field(default_factory=list)
    collection_errors: List[str] = field(default_factory=list)

    @property
    def ref(self) -> ResourceRef:  # pragma: no cover - overridden
        raise NotImplementedError

    def events_with_reason(self, *reasons: str) -> List[Dict[str, Any]]:
        wanted = set(reasons)
        return [e for e in self.events if e.get("reason") in wanted]

    def events_matching(self, pattern: PatternLike, reasons: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
        rx = _compile([pattern])[0]
        pool = self.events_with_reason(*reasons) if reasons else self.events
        return [e for e in pool if rx.search(e.get("message") or "")]

    def warning_events(self) -> List[Dict[str, Any]]:
        return [e for e in self.events if e.get("type") == "Warning"]

    def events_for_container(self, container: str, events: Optional[List[Dict[str, Any]]] = None):
        pool = self.events if events is None else events
        return [e for e in pool if container_from_event(e) == container]


@dataclass
class PodContext(BaseContext):
    scope: ClassVar[Scope] = Scope.POD
    pod: Dict[str, Any] = field(default_factory=dict)
    logs_current: Dict[str, str] = field(default_factory=dict)
    logs_previous: Dict[str, str] = field(default_factory=dict)
    owners: List[Dict[str, Any]] = field(default_factory=list)       # direct owner first
    deployment: Optional[Dict[str, Any]] = None
    node: Optional[Dict[str, Any]] = None
    node_allocation: Optional[Dict[str, Any]] = None
    pvcs: Dict[str, Optional[Dict[str, Any]]] = field(default_factory=dict)   # None == missing
    pvc_events: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    pvs: Dict[str, Optional[Dict[str, Any]]] = field(default_factory=dict)
    storage_classes: Dict[str, Optional[Dict[str, Any]]] = field(default_factory=dict)
    service_account_name: str = "default"
    service_account: Optional[Dict[str, Any]] = None
    service_account_checked: bool = False
    secret_names: Optional[Set[str]] = None      # None == unknown (not collected / RBAC)
    configmap_names: Optional[Set[str]] = None
    metrics: Optional[Dict[str, Dict[str, int]]] = None

    # ---- identity
    @property
    def name(self) -> str:
        return dig(self.pod, "metadata", "name", default="")

    @property
    def namespace(self) -> str:
        return dig(self.pod, "metadata", "namespace", default="default")

    @property
    def ref(self) -> ResourceRef:
        return ResourceRef("Pod", self.name, self.namespace)

    @property
    def spec(self) -> Dict[str, Any]:
        return self.pod.get("spec") or {}

    @property
    def status(self) -> Dict[str, Any]:
        return self.pod.get("status") or {}

    @property
    def phase(self) -> str:
        return self.status.get("phase") or "Unknown"

    @property
    def node_name(self) -> Optional[str]:
        return self.spec.get("nodeName")

    @property
    def ns_flag(self) -> str:
        return f"-n {self.namespace}"

    # ---- containers
    def containers(self, include_init: bool = True) -> List[Dict[str, Any]]:
        return all_containers(self.pod) if include_init else list(self.spec.get("containers") or [])

    def init_container_names(self) -> Set[str]:
        return {c.get("name") for c in self.spec.get("initContainers") or []}

    def statuses(self, include_init: bool = True) -> List[Dict[str, Any]]:
        return all_container_statuses(self.pod) if include_init else list(self.status.get("containerStatuses") or [])

    def status_of(self, container: str) -> Optional[Dict[str, Any]]:
        return next((s for s in self.statuses() if s.get("name") == container), None)

    def spec_of(self, container: str) -> Optional[Dict[str, Any]]:
        return next((c for c in self.containers() if c.get("name") == container), None)

    def total_restarts(self) -> int:
        return sum(int(s.get("restartCount") or 0) for s in self.statuses())

    def is_ready(self) -> bool:
        return (conditions_map(self.pod).get("Ready") or {}).get("status") == "True"

    def is_crashing(self, container: Optional[str] = None) -> bool:
        for st in self.statuses():
            if container and st.get("name") != container:
                continue
            if dig(st, "state", "waiting", "reason") in ("CrashLoopBackOff", "Error") or \
                    (st.get("restartCount") or 0) > 0 or not st.get("ready", True):
                return True
        return False

    # ---- owners
    def top_owner(self) -> Optional[Dict[str, Any]]:
        return self.owners[-1] if self.owners else None

    def owner_label(self) -> Optional[str]:
        if not self.owners:
            return None
        return " <- ".join(f"{o.get('kind')}/{dig(o, 'metadata', 'name')}" for o in reversed(self.owners))

    # ---- logs
    def log_text(self, container: str, previous: bool = False) -> str:
        return (self.logs_previous if previous else self.logs_current).get(container) or ""

    def search_logs(self, patterns: Iterable[PatternLike], containers: Optional[Iterable[str]] = None,
                    sources: Sequence[str] = ("previous", "current"), max_hits: int = 5,
                    exclude: Optional[PatternLike] = None) -> List[LogHit]:
        compiled = _compile(patterns)
        exclude_rx = _compile([exclude])[0] if exclude else None
        wanted = set(containers) if containers else None
        hits: List[LogHit] = []
        seen = set()
        for source in sources:
            logs = self.logs_previous if source == "previous" else self.logs_current
            for cname, text in logs.items():
                if wanted is not None and cname not in wanted or not text:
                    continue
                for idx, line in enumerate(text.splitlines(), 1):
                    if exclude_rx and exclude_rx.search(line):
                        continue
                    if any(rx.search(line) for rx in compiled):
                        key = (cname, _normalize(line))
                        if key in seen:
                            continue
                        seen.add(key)
                        hits.append(LogHit(cname, source, idx, line))
                        if len(hits) >= max_hits:
                            return hits
        return hits

    def last_log_lines(self, container: str, n: int = 3, previous: bool = True) -> List[str]:
        lines = [l for l in self.log_text(container, previous).splitlines() if l.strip()]
        return lines[-n:]


@dataclass
class DeploymentContext(BaseContext):
    scope: ClassVar[Scope] = Scope.DEPLOYMENT
    deployment: Dict[str, Any] = field(default_factory=dict)
    replicasets: List[Dict[str, Any]] = field(default_factory=list)
    pods: List[Dict[str, Any]] = field(default_factory=list)
    quotas: List[Dict[str, Any]] = field(default_factory=list)
    hpa: Optional[Dict[str, Any]] = None

    @property
    def name(self) -> str:
        return dig(self.deployment, "metadata", "name", default="")

    @property
    def namespace(self) -> str:
        return dig(self.deployment, "metadata", "namespace", default="default")

    @property
    def ref(self) -> ResourceRef:
        return ResourceRef("Deployment", self.name, self.namespace)

    def revision_of(self, rs: Dict[str, Any]) -> int:
        try:
            return int(dig(rs, "metadata", "annotations", "deployment.kubernetes.io/revision", default=0))
        except (TypeError, ValueError):
            return 0

    def current_replicaset(self) -> Optional[Dict[str, Any]]:
        rev = dig(self.deployment, "metadata", "annotations", "deployment.kubernetes.io/revision")
        for rs in self.replicasets:
            if str(self.revision_of(rs)) == str(rev):
                return rs
        return max(self.replicasets, key=self.revision_of, default=None)

    def previous_replicaset(self) -> Optional[Dict[str, Any]]:
        current = self.current_replicaset()
        older = [rs for rs in self.replicasets if rs is not current and
                 self.revision_of(rs) < (self.revision_of(current) if current else 1 << 30)]
        return max(older, key=self.revision_of, default=None)


@dataclass
class NodeContext(BaseContext):
    scope: ClassVar[Scope] = Scope.NODE
    node: Dict[str, Any] = field(default_factory=dict)
    allocation: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, int]] = None
    pods: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return dig(self.node, "metadata", "name", default="")

    @property
    def ref(self) -> ResourceRef:
        return ResourceRef("Node", self.name)


@dataclass
class NamespaceContext(BaseContext):
    scope: ClassVar[Scope] = Scope.NAMESPACE
    namespace_obj: Dict[str, Any] = field(default_factory=dict)
    pods: List[Dict[str, Any]] = field(default_factory=list)
    deployments: List[Dict[str, Any]] = field(default_factory=list)
    replicasets: List[Dict[str, Any]] = field(default_factory=list)
    pvcs: List[Dict[str, Any]] = field(default_factory=list)
    storage_classes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    quotas: List[Dict[str, Any]] = field(default_factory=list)
    certificates: Optional[List[Dict[str, Any]]] = None   # None == cert-manager not installed

    @property
    def name(self) -> str:
        return dig(self.namespace_obj, "metadata", "name", default="")

    @property
    def namespace(self) -> str:
        return self.name

    @property
    def ref(self) -> ResourceRef:
        return ResourceRef("Namespace", self.name)


@dataclass
class ClusterContext(BaseContext):
    scope: ClassVar[Scope] = Scope.CLUSTER
    context_name: Optional[str] = None
    server_version: Optional[str] = None
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    pods: List[Dict[str, Any]] = field(default_factory=list)
    deployments: List[Dict[str, Any]] = field(default_factory=list)
    certificates: Optional[List[Dict[str, Any]]] = None
    node_metrics: Optional[Dict[str, Dict[str, int]]] = None

    @property
    def name(self) -> str:
        return self.context_name or "current-context"

    @property
    def ref(self) -> ResourceRef:
        return ResourceRef("Cluster", self.name)

    @property
    def kube_system_pods(self) -> List[Dict[str, Any]]:
        return [p for p in self.pods if dig(p, "metadata", "namespace") == "kube-system"]


__all__ = ["BaseContext", "PodContext", "DeploymentContext", "NodeContext", "NamespaceContext",
           "ClusterContext", "LogHit", "sort_events"]

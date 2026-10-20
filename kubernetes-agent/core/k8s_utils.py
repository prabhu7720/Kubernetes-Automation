"""Pure helper functions for navigating Kubernetes object dictionaries."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .quantity import parse_cpu, parse_memory

PRESSURE_CONDITIONS = ("MemoryPressure", "DiskPressure", "PIDPressure", "NetworkUnavailable")
_BENIGN_WAITING = {"ContainerCreating", "PodInitializing"}


def dig(obj: Any, *keys, default=None):
    cur = obj
    for key in keys:
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list) and isinstance(key, int) and -len(cur) <= key < len(cur):
            cur = cur[key]
        else:
            return default
        if cur is None:
            return default
    return cur


def name_of(obj: Dict[str, Any]) -> str:
    return dig(obj, "metadata", "name", default="") or ""


def namespace_of(obj: Dict[str, Any]) -> Optional[str]:
    return dig(obj, "metadata", "namespace")


def conditions_map(obj: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {c.get("type"): c for c in (dig(obj, "status", "conditions") or []) if c.get("type")}


def node_ready(node: Optional[Dict[str, Any]]) -> Optional[bool]:
    if not node:
        return None
    cond = conditions_map(node).get("Ready")
    if not cond:
        return None
    return cond.get("status") == "True"


def node_pressures(node: Optional[Dict[str, Any]]) -> List[str]:
    if not node:
        return []
    conds = conditions_map(node)
    return [t for t in PRESSURE_CONDITIONS if (conds.get(t) or {}).get("status") == "True"]


def node_summary(node: Optional[Dict[str, Any]]) -> str:
    if not node:
        return "unknown"
    ready = node_ready(node)
    parts = ["Ready" if ready else ("NotReady" if ready is False else "Ready=Unknown")]
    pressures = node_pressures(node)
    parts.append(("pressure: " + ", ".join(pressures)) if pressures else "no pressure conditions")
    if dig(node, "spec", "unschedulable"):
        parts.append("cordoned")
    return "; ".join(parts)


def controller_ref(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    refs = dig(obj, "metadata", "ownerReferences") or []
    for ref in refs:
        if ref.get("controller"):
            return ref
    return refs[0] if refs else None


def selector_to_string(selector: Optional[Dict[str, Any]]) -> str:
    if not selector:
        return ""
    parts = [f"{k}={v}" for k, v in sorted((selector.get("matchLabels") or {}).items())]
    for expr in selector.get("matchExpressions") or []:
        key, op, vals = expr.get("key"), expr.get("operator"), expr.get("values") or []
        if op == "In":
            parts.append(f"{key} in ({','.join(vals)})")
        elif op == "NotIn":
            parts.append(f"{key} notin ({','.join(vals)})")
        elif op == "Exists":
            parts.append(str(key))
        elif op == "DoesNotExist":
            parts.append(f"!{key}")
    return ",".join(parts)


def all_container_statuses(pod: Dict[str, Any]) -> List[Dict[str, Any]]:
    status = pod.get("status") or {}
    return list(status.get("initContainerStatuses") or []) + list(status.get("containerStatuses") or [])


def all_containers(pod: Dict[str, Any]) -> List[Dict[str, Any]]:
    spec = pod.get("spec") or {}
    return list(spec.get("initContainers") or []) + list(spec.get("containers") or [])


def pod_health(pod: Dict[str, Any], restart_threshold: int = 3) -> Tuple[bool, List[str], int]:
    """Heuristic triage: (is_unhealthy, reasons, priority_score)."""
    reasons: List[str] = []
    score = 0
    status = pod.get("status") or {}
    phase = status.get("phase") or "Unknown"
    if phase == "Succeeded":
        return False, [], 0
    if status.get("reason") == "Evicted":
        reasons.append("Evicted")
        score += 50
    if phase in ("Pending", "Failed", "Unknown"):
        reasons.append(f"phase={phase}")
        score += 40
    for st in all_container_statuses(pod):
        cname = st.get("name", "?")
        waiting = dig(st, "state", "waiting", "reason")
        if waiting and waiting not in _BENIGN_WAITING:
            reasons.append(f"{cname}:{waiting}")
            score += 60
        term = dig(st, "state", "terminated")
        if term and term.get("exitCode", 0) != 0:
            reasons.append(f"{cname}:terminated({term.get('reason')},exit={term.get('exitCode')})")
            score += 40
        restarts = st.get("restartCount") or 0
        if restarts >= restart_threshold:
            reasons.append(f"{cname}:restarts={restarts}")
            score += min(restarts, 50)
        if dig(st, "lastState", "terminated", "reason") == "OOMKilled":
            reasons.append(f"{cname}:lastState=OOMKilled")
            score += 30
    if phase == "Running" and not dig(pod, "metadata", "deletionTimestamp"):
        ready = conditions_map(pod).get("Ready")
        if ready and ready.get("status") != "True":
            reasons.append("not-ready")
            score += 30
    reasons = list(dict.fromkeys(reasons))
    return bool(reasons), reasons, score


def container_resources(container: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    res = container.get("resources") or {}
    return {"requests": dict(res.get("requests") or {}), "limits": dict(res.get("limits") or {})}


def resources_line(container: Dict[str, Any]) -> str:
    r = container_resources(container)
    req, lim = r["requests"], r["limits"]
    return (f"requests cpu={req.get('cpu', 'unset')} memory={req.get('memory', 'unset')} | "
            f"limits cpu={lim.get('cpu', 'unset')} memory={lim.get('memory', 'unset')}")


def pod_requests(pod: Dict[str, Any]) -> Dict[str, int]:
    """Effective pod requests/limits: max(sum(app containers), max(init containers))."""
    spec = pod.get("spec") or {}
    totals = {"cpu_requests_m": 0, "memory_requests": 0, "cpu_limits_m": 0, "memory_limits": 0}
    for c in spec.get("containers") or []:
        r = container_resources(c)
        totals["cpu_requests_m"] += parse_cpu(r["requests"].get("cpu")) or 0
        totals["memory_requests"] += parse_memory(r["requests"].get("memory")) or 0
        totals["cpu_limits_m"] += parse_cpu(r["limits"].get("cpu")) or 0
        totals["memory_limits"] += parse_memory(r["limits"].get("memory")) or 0
    for c in spec.get("initContainers") or []:
        r = container_resources(c)
        totals["cpu_requests_m"] = max(totals["cpu_requests_m"], parse_cpu(r["requests"].get("cpu")) or 0)
        totals["memory_requests"] = max(totals["memory_requests"], parse_memory(r["requests"].get("memory")) or 0)
    return totals


def parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        v = re.sub(r"\.\d+", "", str(value)).replace("Z", "+00:00")
        return datetime.fromisoformat(v)
    except ValueError:
        return None


def age_seconds(value: Optional[str]) -> Optional[float]:
    t = parse_time(value)
    if not t:
        return None
    return (datetime.now(timezone.utc) - t).total_seconds()


# ---------------------------------------------------------------- events
def event_count(ev: Dict[str, Any]) -> int:
    return int(ev.get("count") or dig(ev, "series", "count") or 1)


def event_time(ev: Dict[str, Any]) -> str:
    return (ev.get("lastTimestamp") or dig(ev, "series", "lastObservedTime") or ev.get("eventTime")
            or ev.get("firstTimestamp") or dig(ev, "metadata", "creationTimestamp") or "")


def sort_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(events, key=event_time)


def format_event(ev: Dict[str, Any], max_len: int = 300) -> str:
    msg = " ".join((ev.get("message") or "").split())
    if len(msg) > max_len:
        msg = msg[: max_len - 3] + "..."
    when = event_time(ev) or "?"
    return f"Event {ev.get('type', '?')}/{ev.get('reason', '?')} (x{event_count(ev)}, last {when}): {msg}"


def container_from_event(ev: Dict[str, Any]) -> Optional[str]:
    m = re.search(r"\{([^}]+)\}", dig(ev, "involvedObject", "fieldPath") or "")
    return m.group(1) if m else None

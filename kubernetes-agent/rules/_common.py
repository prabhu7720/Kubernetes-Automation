"""Private helpers shared by rule modules (underscore prefix => not loaded as a rule file)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.k8s_utils import container_from_event, dig, parse_time

EXIT_CODES = {
    0: "process exited successfully - for a long-running workload the main process finished unexpectedly",
    1: "generic application error",
    2: "invalid arguments / shell misuse",
    126: "command found but not executable (permissions)",
    127: "command not found (wrong command/entrypoint or missing binary)",
    128: "invalid exit argument",
    130: "SIGINT",
    134: "SIGABRT - process aborted (assertion failure / abort())",
    137: "SIGKILL - killed by the OOM killer or forcibly after the termination grace period",
    139: "SIGSEGV - segmentation fault",
    143: "SIGTERM - asked to stop (liveness probe failure, eviction, scale-down or rollout)",
    255: "fatal error / exit status out of range",
}

# Generic "the app died" log signatures
FATAL_LOG_PATTERNS = [
    r"Traceback \(most recent call last\)",
    r"\bpanic:",
    r"\bfatal\b",
    r"Exception in thread",
    r"unhandled (promise )?rejection",
    r"(?-i:\b[A-Z][A-Za-z0-9]+(Exception|Error)\b)",
    r"\bERROR\b.*\b(failed|cannot|unable|could not|refused|denied|invalid|missing)\b",
    r"segmentation fault",
    r"exec format error",
    r"permission denied",
    r"no such file or directory",
    r"address already in use",
    r"\bOutOfMemoryError\b|heap out of memory",
    r"APPLICATION FAILED TO START",
]


def exit_code_meaning(code: Optional[int]) -> str:
    if code is None:
        return "unknown exit code"
    if code in EXIT_CODES:
        return EXIT_CODES[code]
    if 128 < code < 160:
        return f"terminated by signal {code - 128}"
    return "application-defined error code"


def termination(status: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """Most relevant termination record: current terminated state, else lastState."""
    now = dig(status, "state", "terminated")
    if now:
        return now, "current"
    last = dig(status, "lastState", "terminated")
    if last:
        return last, "last"
    return {}, ""


def waiting(status: Dict[str, Any]) -> Tuple[Optional[str], str]:
    w = dig(status, "state", "waiting") or {}
    return w.get("reason"), (w.get("message") or "")


def run_duration_seconds(term: Dict[str, Any]) -> Optional[float]:
    start, end = parse_time(term.get("startedAt")), parse_time(term.get("finishedAt"))
    if start and end:
        return (end - start).total_seconds()
    return None


def liveness_kill_events(ctx, container: str) -> List[Dict[str, Any]]:
    out = []
    for ev in ctx.events:
        msg = ev.get("message") or ""
        if ev.get("reason") == "Killing" and "liveness probe" in msg.lower():
            c = container_from_event(ev)
            if c in (None, container) and (c == container or container in msg):
                out.append(ev)
    return out


def describe_cmd(ctx) -> str:
    return f"{ctx.cmd} describe pod {ctx.name} -n {ctx.namespace}"


def events_cmd(ctx, name: Optional[str] = None, kind: str = "Pod") -> str:
    return (f"{ctx.cmd} get events -n {ctx.namespace} --field-selector "
            f"involvedObject.kind={kind},involvedObject.name={name or ctx.name} --sort-by=.lastTimestamp")


def logs_cmd(ctx, container: str, previous: bool = False, tail: int = 100) -> str:
    return (f"{ctx.cmd} logs {ctx.name} -n {ctx.namespace} -c {container} --tail={tail}"
            + (" --previous" if previous else ""))


def impact_severity(ctx, container: Optional[str], high, medium):
    """HIGH if the container is crashing / not ready, else MEDIUM."""
    return high if ctx.is_crashing(container) or not ctx.is_ready() else medium

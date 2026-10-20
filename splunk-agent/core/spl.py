"""SPL helpers: quoting, pipe splitting and a local (offline) linter."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

_SAFE_FIELD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SAFE_VALUE = re.compile(r"^[\w\-.*]+$")

GENERATING_COMMANDS = frozenset({
    "tstats", "mstats", "mcatalog", "inputlookup", "rest", "makeresults", "metadata", "datamodel", "from",
    "dbinspect", "eventcount", "loadjob", "pivot", "search", "savedsearch", "multisearch", "union",
    "mpreview", "inputcsv", "gentimes", "set", "metasearch", "tstats",
})
DANGEROUS_COMMANDS = {
    "delete": "error", "script": "error", "run": "error", "runshellscript": "error",
    "sendemail": "warning", "outputlookup": "warning", "outputcsv": "warning", "collect": "warning",
    "mcollect": "warning", "meventcollect": "warning", "tscollect": "warning", "sendalert": "warning",
}
EXPENSIVE_COMMANDS = {"join", "transaction", "append", "appendcols", "map", "localize", "cluster"}


def quote_eval_field(name: str) -> str:
    """Quote a field name for eval/where context (single quotes when it has dots, dashes, ...)."""
    return name if _SAFE_FIELD.match(name) else "'" + name.replace("'", "\\'") + "'"


def quote_value(value: object) -> str:
    """Quote a value for search-time comparisons."""
    text = str(value)
    if _SAFE_VALUE.match(text):
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def split_pipes(spl: str) -> list[str]:
    """Split SPL on top-level pipes (ignores pipes inside quotes and [subsearches])."""
    stages: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    depth = 0
    escaped = False
    for ch in spl:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == "\\":
            buf.append(ch)
            escaped = True
            continue
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth = max(0, depth - 1)
        elif ch == "|" and depth == 0:
            stages.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    stages.append("".join(buf))
    return stages


def command_of(stage: str) -> str:
    parts = stage.strip().split(None, 1)
    return parts[0].lower() if parts else ""


@dataclass(frozen=True)
class LintIssue:
    level: str  # error | warning | info
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _balance_issues(spl: str) -> list[LintIssue]:
    issues: list[LintIssue] = []
    quote: str | None = None
    escaped = False
    depth = {"(": 0, "[": 0}
    closing = {")": "(", "]": "["}
    for ch in spl:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch == '"':
            quote = ch
        elif ch in depth:
            depth[ch] += 1
        elif ch in closing:
            depth[closing[ch]] -= 1
            if depth[closing[ch]] < 0:
                issues.append(LintIssue("error", "unbalanced", f"Unexpected '{ch}'"))
                depth[closing[ch]] = 0
    if quote:
        issues.append(LintIssue("error", "unbalanced", "Unterminated double quote"))
    for opener, count in depth.items():
        if count > 0:
            issues.append(LintIssue("error", "unbalanced", f"{count} unclosed '{opener}'"))
    return issues


def lint(spl: str) -> list[LintIssue]:
    """Offline static checks.  Remote validation (search/parser) is available via SplunkClient.parse."""
    issues: list[LintIssue] = []
    if not spl or not spl.strip():
        return [LintIssue("error", "empty", "Search is empty")]
    if "{{" in spl or "}}" in spl:
        issues.append(LintIssue("error", "unresolved_placeholder", "Template placeholder left unresolved"))
    issues.extend(_balance_issues(spl))

    stages = split_pipes(spl)
    leading_pipe = spl.lstrip().startswith("|")
    if leading_pipe:
        stages = stages[1:]
    for i, stage in enumerate(stages):
        if not stage.strip():
            issues.append(LintIssue("error", "empty_stage", f"Empty pipeline stage at position {i + 1}"))
    if not stages:
        return issues

    first = stages[0]
    if leading_pipe:
        cmd = command_of(first)
        if cmd not in GENERATING_COMMANDS:
            issues.append(LintIssue("warning", "not_generating", f"'{cmd}' is not a generating command"))
    else:
        if not re.search(r"\bindex\s*=", first, re.IGNORECASE):
            issues.append(LintIssue("warning", "no_index", "No index specified - search will use default indexes"))
        if re.search(r"\bindex\s*=\s*\*(?=\s|\)|$)", first):
            issues.append(LintIssue("warning", "all_indexes", "index=* scans every index; scope it if possible"))
        if re.search(r"=\s*\"?\*[^\s\"]", first):
            issues.append(LintIssue("info", "leading_wildcard", "Leading wildcard in a field value is slow"))

    for stage in stages[1:] if not leading_pipe else stages:
        cmd = command_of(stage)
        if cmd in DANGEROUS_COMMANDS:
            issues.append(LintIssue(DANGEROUS_COMMANDS[cmd], "dangerous_command",
                                    f"'{cmd}' modifies data or executes actions"))
        elif cmd in EXPENSIVE_COMMANDS:
            issues.append(LintIssue("warning", "expensive_command", f"'{cmd}' is expensive at scale"))
    return issues

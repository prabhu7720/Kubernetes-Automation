"""Redaction of sensitive values in evidence before it is printed or saved.

Logs frequently contain credentials (connection strings, bearer tokens,
passwords in stack traces). Everything is processed locally, but reports are
often pasted into tickets/Slack, so evidence is scrubbed before rendering.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Pattern, Tuple

REDACTED = "***REDACTED***"

_DEFAULT_RULES: List[Tuple[Pattern, str]] = [
    # key=value / key: value / "key":"value"
    (re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
                r"client[_-]?secret|private[_-]?key|authorization)(\"?\s*[:=]\s*\"?)([^\s\"',;&}]+)"),
     r"\1\2" + REDACTED),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/]+=*"), "Bearer " + REDACTED),
    (re.compile(r"(?i)\bbasic\s+[A-Za-z0-9+/]{8,}=*"), "Basic " + REDACTED),
    # JWTs
    (re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"), REDACTED),
    # AWS access key ids
    (re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"), REDACTED),
    # credentials embedded in URLs: scheme://user:pass@host
    (re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)[^:/\s@]+:[^@\s/]+@"), r"\1" + REDACTED + "@"),
]


class Redactor:
    def __init__(self, extra_patterns: Optional[Iterable[str]] = None, max_line_length: int = 400):
        self.rules = list(_DEFAULT_RULES)
        for pattern in extra_patterns or []:
            self.rules.append((re.compile(pattern), REDACTED))
        self.max_line_length = max_line_length

    def redact(self, text: Optional[str], truncate: bool = True) -> str:
        if not text:
            return text or ""
        out = str(text)
        for rx, repl in self.rules:
            out = rx.sub(repl, out)
        if truncate and self.max_line_length and len(out) > self.max_line_length:
            out = out[: self.max_line_length - 3] + "..."
        return out

    def redact_all(self, lines: Iterable[str]) -> List[str]:
        return [self.redact(line) for line in lines]

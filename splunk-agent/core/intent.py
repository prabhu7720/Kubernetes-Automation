"""Rule-based natural-language intent parser (fully offline).

Extracts from a free-text request:
  * the artifact type (search, report, alert, dashboard, saved search, correlation, runbook)
  * time range ("last 24 hours", "yesterday" ...)
  * thresholds/comparators ("exceed 100", "below 5%")
  * evaluation window ("per hour", "in 10 minutes")
  * HTTP status codes, top-N limit, group-by entity, field filters
  * severity, schedule and an explicit title
and returns content tokens for the use-case matcher.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from core.exceptions import IntentResolutionError
from core.models import ArtifactType, Severity
from core.nlp import normalize, stem

_UNIT_RE = r"(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?)"
_UNIT_PREFIX = (("second", "s"), ("sec", "s"), ("minute", "m"), ("min", "m"), ("hour", "h"),
                ("hr", "h"), ("day", "d"), ("week", "w"), ("month", "mon"))

_TIME_RE = re.compile(r"\b(?:(?:in|over|during|for|within|from)\s+)?(?:the\s+)?(?:last|past|previous|prior)\s+"
                      r"(?:(\d+)\s*)?" + _UNIT_RE + r"\b")
_TIME_WORDS = [
    (re.compile(r"\btoday\b"), ("@d", "now", "today")),
    (re.compile(r"\byesterday\b"), ("-1d@d", "@d", "yesterday")),
    (re.compile(r"\bthis\s+week\b"), ("@w0", "now", "this week")),
    (re.compile(r"\bthis\s+month\b"), ("@mon", "now", "this month")),
]
_WINDOW_RE = re.compile(r"\b(?:per|every|each|within|in)\s+(?:an?\s+|the\s+)?(?:(\d+)\s*)?" + _UNIT_RE + r"\b")
_THRESH_RE = re.compile(
    r"(?P<op>exceed(?:s|ed|ing)?|go(?:es)?\s+above|go(?:es)?\s+over|above|over|more\s+than|greater\s+than|"
    r"higher\s+than|at\s+least|surpass(?:es)?|reach(?:es)?|cross(?:es)?|>=|>|drops?\s+below|falls?\s+below|"
    r"below|under|less\s+than|fewer\s+than|lower\s+than|<=|<)\s*"
    r"(?P<num>\d+(?:\.\d+)?)(?![\d.])(?!\s*" + _UNIT_RE + r"\b)\s*(?P<pct>%|percent)?")
_STATUS_RES = [
    re.compile(r"\b(?:http|status|statuscode|code|response)s?\s+(?:code\s+)?([1-5](?:\d\d|xx))\b"),
    re.compile(r"\b([1-5](?:\d\d|xx))\s+(?:errors?|status|statuscode|responses?|codes?|trends?)\b"),
    re.compile(r"\b([1-5]xx)\b"),
]
_TOP_N_RE = re.compile(r"\b(?:top|first|limit)\s+(\d{1,4})\b")
_TOP_ENTITY_RE = re.compile(r"\btop\s+(?:\d+\s+)?([a-z]+(?:\s+[a-z]+)?)")
_BY_RE = re.compile(r"\bby\s+([a-z][a-z0-9_]*(?:\s+[a-z][a-z0-9_]*)?)")
_EXPLICIT_FILTER_RE = re.compile(r"(?<![\w.])([A-Za-z_][\w.]*)\s*(!=|=)\s*(\"[^\"]*\"|'[^']*'|[^\s,;)]+)")
_NATURAL_FILTER_RE = re.compile(
    r"\b(?:in|for|on|from|within)\s+(?:the\s+)?(namespace|environment|env|host|server|user|account|app|"
    r"application|service|cluster|region|index|sourcetype)\s+[\"']?([a-z0-9][\w\-.*]*)[\"']?")
_SEVERITY_RES = [
    re.compile(r"\b(critical|high|medium|low|informational|info)[\s-]+(?:severity|priority|sev)\b"),
    re.compile(r"\b(?:severity|priority|sev)\s*[:=]?\s*(critical|high|medium|low|info)\b"),
]
_PRIORITY_RE = re.compile(r"\b(p[1-4]|sev[1-4])\b")
_SCHEDULE_RES = [
    (re.compile(r"\bhourly\b|\bevery\s+hour\b"), "0 * * * *"),
    (re.compile(r"\bnightly\b|\bevery\s+night\b"), "0 1 * * *"),
    (re.compile(r"\bdaily\b|\bevery\s+day\b|\bevery\s+morning\b"), "0 6 * * *"),
    (re.compile(r"\bweekly\b|\bevery\s+week\b|\bevery\s+monday\b"), "0 7 * * 1"),
    (re.compile(r"\bmonthly\b|\bevery\s+month\b"), "0 7 1 * *"),
]
_TITLE_RE = re.compile(r"\b(?:called|named|titled)\s+(?:\"([^\"]+)\"|'([^']+)'|([\w\- ]+)$)", re.IGNORECASE)
_ARTIFACT_PATTERNS: list[tuple[ArtifactType, re.Pattern[str]]] = [
    (ArtifactType.DASHBOARD, re.compile(r"\bdash\s?boards?\b")),
    (ArtifactType.CORRELATION, re.compile(r"\bcorrelation(?:\s+search(?:es)?|\s+rules?)?\b|\bnotables?\b|\bes\s+detections?\b")),
    (ArtifactType.RUNBOOK, re.compile(r"\brun\s?books?\b|\bplay\s?books?\b|\bsop\b")),
    (ArtifactType.SAVED_SEARCH, re.compile(r"\bsaved\s+search(?:es)?\b|\bsave\s+(?:it|this|the\s+search|as\s+(?:a\s+)?search)\b")),
    (ArtifactType.ALERT, re.compile(r"\balert(?:s|ing)?\b|\bnotify\b|\bnotification\b|\bpage\s+(?:me|on-?call)\b|\bwarn\s+me\b")),
    (ArtifactType.REPORT, re.compile(r"\breports?\b|\bscheduled\s+summary\b")),
]
_FILTER_VALUE_STOP = {"health", "activity", "error", "errors", "events", "logs", "metrics", "dashboard",
                      "alert", "report", "the", "all", "issues", "failures"}

DEFAULT_GROUPBY_ALIASES: dict[str, str] = {
    "user": "user", "account": "user", "username": "user", "src": "src", "source ip": "src", "ip": "src",
    "client": "src", "client ip": "src", "host": "host", "application": "application", "service": "application",
    "pod": "pod", "namespace": "namespace", "node": "node", "container": "container",
    "status": "status_code", "statuscode": "status_code", "uri": "uri", "endpoint": "uri", "url": "uri",
    "path": "uri", "dest": "dest", "destination": "dest", "region": "region", "sourcetype": "sourcetype",
    "index": "index", "cluster": "cluster", "environment": "environment", "env": "environment",
    "reason": "reason", "signature": "signature", "deployment": "object_name", "process": "process",
}
_FILTER_KEY_ALIASES = {"env": "environment", "server": "host", "account": "user", "app": "application",
                       "service": "application"}


@dataclass(frozen=True)
class TimeRange:
    earliest: str
    latest: str = "now"
    label: str = ""


@dataclass(frozen=True)
class FieldFilter:
    field: str
    value: str
    op: str = "="


@dataclass
class Intent:
    text: str
    artifact_type: ArtifactType
    tokens: list[str]
    time_range: TimeRange | None = None
    threshold: float | None = None
    comparator: str | None = None
    percent: bool = False
    window: str | None = None
    status_codes: list[str] = field(default_factory=list)
    limit: int | None = None
    groupby: str | None = None
    filters: list[FieldFilter] = field(default_factory=list)
    severity: Severity | None = None
    schedule: str | None = None
    title: str | None = None

    @property
    def index_filters(self) -> list[str]:
        return [f.value for f in self.filters if f.field == "index" and f.op == "="]

    @property
    def sourcetype_filters(self) -> list[str]:
        return [f.value for f in self.filters if f.field == "sourcetype" and f.op == "="]

    @property
    def field_filters(self) -> list[FieldFilter]:
        return [f for f in self.filters if f.field not in ("index", "sourcetype")]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["artifact_type"] = self.artifact_type.value
        d["severity"] = self.severity.value if self.severity else None
        return d


def _unit(word: str) -> str:
    for prefix, unit in _UNIT_PREFIX:
        if word.startswith(prefix):
            return unit
    raise ValueError(word)


def _blank(text: str, start: int, end: int) -> str:
    return text[:start] + " " * (end - start) + text[end:]


class IntentParser:
    """Converts free text into a structured :class:`Intent`."""

    def __init__(self, groupby_aliases: Mapping[str, str] | None = None) -> None:
        self.groupby_aliases = {**DEFAULT_GROUPBY_ALIASES, **(groupby_aliases or {})}

    # ------------------------------------------------------------------ public
    def parse(self, text: str) -> Intent:
        if not text or not text.strip():
            raise IntentResolutionError("Empty request")
        original = " " + text.strip() + " "
        lower = original.lower()
        work = lower

        artifact = self._artifact_type(lower)
        filters, work = self._filters(original, work)
        time_range, work = self._time_range(work)
        window, work = self._window(work)
        threshold, comparator, percent, work = self._threshold(work)
        if artifact is ArtifactType.SEARCH and threshold is not None and re.search(r"\b(when|if|whenever)\b", lower):
            artifact = ArtifactType.ALERT
        severity = self._severity(lower)
        schedule = next((cron for rx, cron in _SCHEDULE_RES if rx.search(lower)), None)
        title_match = _TITLE_RE.search(text)
        title = next((g for g in title_match.groups() if g), None).strip() if title_match else None
        if title_match:
            work = work.replace(title_match.group(0).lower(), " ")

        limit_match = _TOP_N_RE.search(work)
        limit = int(limit_match.group(1)) if limit_match else None
        if limit_match:
            work = _blank(work, *limit_match.span(1))

        return Intent(
            text=text.strip(),
            artifact_type=artifact,
            tokens=normalize(work),
            time_range=time_range,
            threshold=threshold,
            comparator=comparator,
            percent=percent,
            window=window,
            status_codes=self._status_codes(work),
            limit=limit,
            groupby=self._groupby(work),
            filters=filters,
            severity=severity,
            schedule=schedule,
            title=title,
        )

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _artifact_type(lower: str) -> ArtifactType:
        for artifact, pattern in _ARTIFACT_PATTERNS:
            if pattern.search(lower):
                return artifact
        return ArtifactType.SEARCH

    @staticmethod
    def _time_range(work: str) -> tuple[TimeRange | None, str]:
        m = _TIME_RE.search(work)
        if m:
            n = int(m.group(1) or 1)
            unit = _unit(m.group(2))
            label = f"last {n} {m.group(2)}"
            return TimeRange(f"-{n}{unit}", "now", label), _blank(work, *m.span())
        for pattern, (earliest, latest, label) in _TIME_WORDS:
            m = pattern.search(work)
            if m:
                return TimeRange(earliest, latest, label), _blank(work, *m.span())
        return None, work

    @staticmethod
    def _window(work: str) -> tuple[str | None, str]:
        m = _WINDOW_RE.search(work)
        if not m:
            return None, work
        n = int(m.group(1) or 1)
        unit = _unit(m.group(2))
        if unit == "s":
            n, unit = max(1, n // 60), "m"
        if unit == "mon":
            n, unit = 30 * n, "d"
        return f"{n}{unit}", _blank(work, *m.span())

    @staticmethod
    def _threshold(work: str) -> tuple[float | None, str | None, bool, str]:
        m = _THRESH_RE.search(work)
        if not m:
            return None, None, False, work
        op = re.sub(r"\s+", " ", m.group("op"))
        if op == ">=" or op.startswith(("at least", "reach")):
            comparator = ">="
        elif op == "<=":
            comparator = "<="
        elif op == "<" or op.startswith(("drop", "fall", "below", "under", "less", "fewer", "lower")):
            comparator = "<"
        else:
            comparator = ">"
        return float(m.group("num")), comparator, bool(m.group("pct")), _blank(work, *m.span())

    @staticmethod
    def _status_codes(work: str) -> list[str]:
        codes: list[str] = []
        for pattern in _STATUS_RES:
            for m in pattern.finditer(work):
                code = m.group(1).replace("xx", "*")
                if code not in codes:
                    codes.append(code)
        return codes

    def _lookup_entity(self, phrase: str) -> str | None:
        words = phrase.split()
        candidates = [" ".join(words[:2]), words[0]] if len(words) > 1 else [words[0]] if words else []
        for cand in candidates:
            for key in (cand, " ".join(stem(w) for w in cand.split())):
                if key in self.groupby_aliases:
                    return self.groupby_aliases[key]
        return None

    def _groupby(self, work: str) -> str | None:
        for m in _BY_RE.finditer(work):
            entity = self._lookup_entity(m.group(1))
            if entity:
                return entity
        m = _TOP_ENTITY_RE.search(work)
        if m:
            return self._lookup_entity(m.group(1))
        return None

    @staticmethod
    def _severity(lower: str) -> Severity | None:
        for pattern in _SEVERITY_RES:
            m = pattern.search(lower)
            if m:
                value = m.group(1)
                return Severity.INFO if value.startswith("info") else Severity.parse(value)
        m = _PRIORITY_RE.search(lower)
        if m:
            return {"1": Severity.CRITICAL, "2": Severity.HIGH, "3": Severity.MEDIUM, "4": Severity.LOW}[m.group(1)[-1]]
        return None

    @staticmethod
    def _filters(original: str, work: str) -> tuple[list[FieldFilter], str]:
        filters: list[FieldFilter] = []
        for m in _EXPLICIT_FILTER_RE.finditer(original):
            key, op, value = m.group(1), m.group(2), m.group(3).strip("\"'")
            filters.append(FieldFilter(_FILTER_KEY_ALIASES.get(key.lower(), key), value, op))
            if len(original) == len(work):
                work = _blank(work, *m.span())
        for m in _NATURAL_FILTER_RE.finditer(work):
            key, value = m.group(1), m.group(2)
            if value in _FILTER_VALUE_STOP:
                continue
            filters.append(FieldFilter(_FILTER_KEY_ALIASES.get(key, key), value))
            work = _blank(work, *m.span())
        return filters, work

"""Domain models shared by rule packs, generators and the agent.

A *use case* is the unit of capability: a parameterised SPL template plus the
metadata needed to turn it into reports, alerts, dashboard panels, correlation
searches and runbooks.  Templates reference logical (canonical) field names
through placeholders which are resolved against the discovered catalog:

    {{base}}            index/sourcetype clause chosen by the resolver
    {{index}}           index clause only (for tstats/mstats "raw" templates)
    {{time}}            inline earliest/latest (ad-hoc searches only)
    {{f.user}}          actual field name for canonical field "user"
    {{q.user}}          same, quoted for eval/where context
    {{m.cpu}}           actual metric name for canonical metric "cpu"
    {{p.status}}        use-case parameter (overridable from the request/config)
    {{groupby}}         group-by field (default from use case, overridable by "by X")
    {{span}} {{limit}} {{threshold}} {{comparator}} {{extra_filter}}
    {{enrich.threat_intel}}  optional lookup clause if a matching lookup exists
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields, replace
from functools import cached_property
from typing import Any, Mapping

from core.compat import StrEnum

TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z_][\w.]*)\s*\}\}")
_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,79}$")
_TOKEN_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
WINDOW_RE = re.compile(r"^(\d+)([smhdw])$")
COMPARATORS = (">", ">=", "<", "<=", "=", "!=")
KINDS = ("events", "raw")


def _as_tuple(value: Any) -> tuple:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)


def _checked(cls: type, data: Mapping[str, Any], what: str) -> dict[str, Any]:
    names = {f.name for f in fields(cls)}
    unknown = set(data) - names
    if unknown:
        raise ValueError(f"Unknown {what} attribute(s): {', '.join(sorted(unknown))}")
    return dict(data)


def format_number(value: float | int) -> str:
    value = float(value)
    return str(int(value)) if value.is_integer() else f"{value:g}"


# --------------------------------------------------------------------------- enums
class ArtifactType(StrEnum):
    SEARCH = "search"
    REPORT = "report"
    ALERT = "alert"
    DASHBOARD = "dashboard"
    SAVED_SEARCH = "saved_search"
    CORRELATION = "correlation"
    RUNBOOK = "runbook"


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def splunk_level(self) -> int:
        """savedsearches.conf alert.severity (1 debug .. 6 fatal)."""
        return {"info": 2, "low": 3, "medium": 4, "high": 5, "critical": 6}[self.value]

    @property
    def es_severity(self) -> str:
        return "informational" if self is Severity.INFO else self.value

    @classmethod
    def parse(cls, value: "Severity | str") -> "Severity":
        if isinstance(value, Severity):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError as exc:
            raise ValueError(f"Invalid severity {value!r}") from exc


class Visualization(StrEnum):
    TABLE = "table"
    LINE = "line"
    AREA = "area"
    COLUMN = "column"
    BAR = "bar"
    PIE = "pie"
    SINGLE = "single"
    EVENTS = "events"

    @property
    def studio_type(self) -> str:
        return "splunk.singlevalue" if self is Visualization.SINGLE else f"splunk.{self.value}"

    @property
    def is_chart(self) -> bool:
        return self in (Visualization.LINE, Visualization.AREA, Visualization.COLUMN,
                        Visualization.BAR, Visualization.PIE)

    @property
    def panel_kind(self) -> str:
        if self is Visualization.SINGLE:
            return "kpi"
        if self in (Visualization.TABLE, Visualization.EVENTS):
            return "table"
        return "chart"

    def saved_search_display(self) -> dict[str, str]:
        if self is Visualization.TABLE:
            return {"display.general.type": "statistics", "display.page.search.tab": "statistics"}
        if self is Visualization.EVENTS:
            return {"display.general.type": "events"}
        if self is Visualization.SINGLE:
            return {"display.general.type": "visualizations", "display.page.search.tab": "visualizations",
                    "display.visualizations.type": "singlevalue"}
        return {"display.general.type": "visualizations", "display.page.search.tab": "visualizations",
                "display.visualizations.type": "charting",
                "display.visualizations.charting.chart": self.value}

    @classmethod
    def parse(cls, value: "Visualization | str") -> "Visualization":
        if isinstance(value, Visualization):
            return value
        text = str(value).strip().lower().replace("splunk.", "")
        text = {"singlevalue": "single", "single_value": "single", "kpi": "single"}.get(text, text)
        try:
            return cls(text)
        except ValueError as exc:
            raise ValueError(f"Invalid visualization {value!r}") from exc


# --------------------------------------------------------------------------- specs
@dataclass(frozen=True)
class AlertSpec:
    threshold: float = 0
    metric: str = "count"
    comparator: str = ">"
    severity: Severity = Severity.MEDIUM
    window: str = "1h"
    pipeline: str | None = None
    lookback: str | None = None
    throttle_fields: tuple[str, ...] = ()
    suppress_period: str = "1h"
    recommended_actions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.comparator not in COMPARATORS:
            raise ValueError(f"Invalid comparator {self.comparator!r}")
        if not WINDOW_RE.match(self.window):
            raise ValueError(f"Invalid alert window {self.window!r} (expected e.g. 5m, 1h, 1d)")
        object.__setattr__(self, "severity", Severity.parse(self.severity))
        object.__setattr__(self, "threshold", float(self.threshold))
        object.__setattr__(self, "throttle_fields", _as_tuple(self.throttle_fields))
        object.__setattr__(self, "recommended_actions", _as_tuple(self.recommended_actions))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AlertSpec":
        return cls(**_checked(cls, data, "alert"))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass(frozen=True)
class RunbookSpec:
    triage: tuple[str, ...] = ()
    investigation: tuple[str, ...] = ()
    remediation: tuple[str, ...] = ()
    escalation: str = ""
    references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("triage", "investigation", "remediation", "references"):
            object.__setattr__(self, name, _as_tuple(getattr(self, name)))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RunbookSpec":
        return cls(**_checked(cls, data, "runbook"))


@dataclass(frozen=True)
class UseCase:
    id: str
    name: str
    domain: str
    description: str
    datasource: str
    keywords: tuple[str, ...]
    filter: str = ""
    pipeline: str = ""
    kind: str = "events"
    visualization: Visualization = Visualization.TABLE
    groupby: str | None = None
    params: Mapping[str, Any] = field(default_factory=dict)
    default_earliest: str = "-24h"
    default_span: str = "1h"
    default_limit: int = 10
    report_cron: str = "0 6 * * *"
    alert: AlertSpec | None = None
    tstats: str | None = None
    single_value: str | None = None
    runbook: RunbookSpec | None = None
    correlation: bool = False
    security_domain: str | None = None
    risk_object: tuple[str, str] | None = None
    risk_score: int = 40
    mitre: tuple[str, ...] = ()
    related: tuple[str, ...] = ()
    business_value: str = ""
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _ID_RE.match(self.id):
            raise ValueError(f"Invalid use case id {self.id!r} (lowercase, digits, underscore)")
        if self.kind not in KINDS:
            raise ValueError(f"{self.id}: kind must be one of {KINDS}")
        for name in ("keywords", "mitre", "related", "tags"):
            object.__setattr__(self, name, _as_tuple(getattr(self, name)))
        if not self.keywords:
            raise ValueError(f"{self.id}: at least one keyword is required")
        if self.kind == "raw" and not self.pipeline.strip():
            raise ValueError(f"{self.id}: raw use cases need a full pipeline")
        if self.kind == "events" and not (self.filter.strip() or self.pipeline.strip()):
            raise ValueError(f"{self.id}: events use cases need a filter or pipeline")
        object.__setattr__(self, "visualization", Visualization.parse(self.visualization))
        object.__setattr__(self, "params", dict(self.params or {}))
        if isinstance(self.alert, Mapping):
            object.__setattr__(self, "alert", AlertSpec.from_dict(self.alert))
        if isinstance(self.runbook, Mapping):
            object.__setattr__(self, "runbook", RunbookSpec.from_dict(self.runbook))
        if self.risk_object is not None:
            ro = tuple(self.risk_object)
            if len(ro) != 2:
                raise ValueError(f"{self.id}: risk_object must be (field, type)")
            object.__setattr__(self, "risk_object", ro)

    def __hash__(self) -> int:  # identity is the id (params/alert are unhashable mappings)
        return hash(self.id)

    # ----------------------------------------------------------------- derived
    @cached_property
    def placeholders(self) -> frozenset[str]:
        parts = [self.filter, self.pipeline, self.tstats or "", self.single_value or ""]
        if self.alert and self.alert.pipeline:
            parts.append(self.alert.pipeline)
        return frozenset(TOKEN_RE.findall("\n".join(parts)))

    @property
    def required_fields(self) -> set[str]:
        out = {p.split(".", 1)[1] for p in self.placeholders if p.startswith(("f.", "q."))}
        if self.groupby:
            out.add(self.groupby)
        if self.alert:
            out.update(self.alert.throttle_fields)
        return out

    @property
    def required_metrics(self) -> set[str]:
        return {p.split(".", 1)[1] for p in self.placeholders if p.startswith("m.")}

    @property
    def uses_groupby(self) -> bool:
        return bool({"groupby", "qgroupby"} & self.placeholders)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, domain: str | None = None) -> "UseCase":
        data = dict(data)
        if domain and "domain" not in data:
            data["domain"] = domain
        return cls(**_checked(cls, data, "use case"))

    def with_overrides(self, overrides: Mapping[str, Any]) -> "UseCase":
        o = dict(overrides)
        if "params" in o:
            o["params"] = {**self.params, **(o["params"] or {})}
        if isinstance(o.get("alert"), Mapping):
            base = self.alert.to_dict() if self.alert else {}
            o["alert"] = AlertSpec.from_dict({**base, **o["alert"]})
        _checked(UseCase, o, "use case override")
        return replace(self, **o)


@dataclass(frozen=True)
class PanelSpec:
    use_case: str
    title: str | None = None
    visualization: Visualization | None = None
    pipeline: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        if self.visualization is not None:
            object.__setattr__(self, "visualization", Visualization.parse(self.visualization))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | str) -> "PanelSpec":
        if isinstance(data, str):
            return cls(use_case=data)
        return cls(**_checked(cls, data, "panel"))


@dataclass(frozen=True)
class InputSpec:
    token: str
    label: str
    field: str
    default: str = "*"

    def __post_init__(self) -> None:
        if not _TOKEN_NAME_RE.match(self.token):
            raise ValueError(f"Invalid dashboard token {self.token!r}")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "InputSpec":
        return cls(**_checked(cls, data, "input"))


@dataclass(frozen=True)
class DashboardBlueprint:
    id: str
    title: str
    description: str
    domain: str
    keywords: tuple[str, ...]
    panels: tuple[PanelSpec, ...]
    inputs: tuple[InputSpec, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _ID_RE.match(self.id):
            raise ValueError(f"Invalid blueprint id {self.id!r}")
        object.__setattr__(self, "keywords", _as_tuple(self.keywords))
        object.__setattr__(self, "tags", _as_tuple(self.tags))
        object.__setattr__(self, "panels", tuple(
            p if isinstance(p, PanelSpec) else PanelSpec.from_dict(p) for p in self.panels))
        object.__setattr__(self, "inputs", tuple(
            i if isinstance(i, InputSpec) else InputSpec.from_dict(i) for i in self.inputs))
        if not self.panels:
            raise ValueError(f"Blueprint {self.id} has no panels")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, domain: str | None = None) -> "DashboardBlueprint":
        data = dict(data)
        if domain and "domain" not in data:
            data["domain"] = domain
        return cls(**_checked(cls, data, "dashboard blueprint"))

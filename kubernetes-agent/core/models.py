"""Core data models shared by collectors, rules, analyzers and reporting."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class Severity(enum.IntEnum):
    """Ordered severity levels. Higher value == more severe."""

    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @property
    def label(self) -> str:
        return self.name.capitalize()

    @classmethod
    def parse(cls, value: Any) -> "Severity":
        if isinstance(value, Severity):
            return value
        try:
            return cls[str(value).strip().upper()]
        except KeyError as exc:
            valid = ", ".join(s.name.lower() for s in cls)
            raise ValueError(f"Unknown severity '{value}'. Valid values: {valid}") from exc


class Scope(str, enum.Enum):
    """The kind of context a rule is evaluated against."""

    POD = "pod"
    DEPLOYMENT = "deployment"
    NODE = "node"
    NAMESPACE = "namespace"
    CLUSTER = "cluster"


@dataclass(frozen=True)
class ResourceRef:
    kind: str
    name: str
    namespace: Optional[str] = None

    @property
    def display(self) -> str:
        return f"{self.namespace}/{self.name}" if self.namespace else self.name

    def __str__(self) -> str:
        return f"{self.kind} {self.display}"

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "name": self.name, "namespace": self.namespace}


@dataclass
class Finding:
    """A single diagnosed issue produced by a rule."""

    rule_id: str
    title: str
    severity: Severity
    resource: ResourceRef
    root_cause: str
    evidence: List[str] = field(default_factory=list)
    confidence: int = 50
    recommendations: List[str] = field(default_factory=list)
    validation_commands: List[str] = field(default_factory=list)
    container: Optional[str] = None
    is_symptom: bool = False
    category: str = "general"
    # Findings sharing a correlation key describe the same underlying problem
    # (e.g. "secret:payments/db-creds"). The analyzer keeps the strongest one as
    # primary and marks the rest as symptoms.
    correlation_key: Optional[str] = None
    related: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.confidence = max(0, min(100, int(self.confidence)))
        self.severity = Severity.parse(self.severity)

    def sort_key(self):
        return (-int(self.severity), self.is_symptom, -self.confidence, self.rule_id)

    def fingerprint(self):
        return (self.rule_id, str(self.resource), self.container, self.title, self.root_cause)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "severity": self.severity.label,
            "resource": self.resource.to_dict(),
            "container": self.container,
            "category": self.category,
            "root_cause": self.root_cause,
            "evidence": list(self.evidence),
            "confidence": self.confidence,
            "recommendations": list(self.recommendations),
            "validation_commands": list(self.validation_commands),
            "is_symptom": self.is_symptom,
            "related": list(self.related),
        }


@dataclass
class AnalysisResult:
    """Result for one resource; may contain child results (e.g. pods of a deployment)."""

    resource: ResourceRef
    facts: List[str] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    children: List["AnalysisResult"] = field(default_factory=list)
    collection_errors: List[str] = field(default_factory=list)

    def all_findings(self) -> List[Finding]:
        out = list(self.findings)
        for child in self.children:
            out.extend(child.all_findings())
        return out

    @property
    def severity(self) -> Optional[Severity]:
        findings = self.all_findings()
        return max((f.severity for f in findings), default=None)

    @property
    def primary(self) -> Optional[Finding]:
        candidates = sorted(self.all_findings(), key=lambda f: f.sort_key())
        return candidates[0] if candidates else None

    def to_dict(self) -> Dict[str, Any]:
        sev = self.severity
        return {
            "resource": self.resource.to_dict(),
            "severity": sev.label if sev is not None else "Healthy",
            "facts": list(self.facts),
            "findings": [f.to_dict() for f in sorted(self.findings, key=lambda f: f.sort_key())],
            "collection_errors": list(self.collection_errors),
            "children": [c.to_dict() for c in self.children],
        }

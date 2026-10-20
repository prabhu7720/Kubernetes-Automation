"""Enterprise Security correlation searches (notable + risk-based alerting)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from core.models import ArtifactType, Severity
from core.schedule import describe_cron
from generators.alert_generator import build_alert_search
from generators.base import Artifact, ArtifactGenerator, GenerationRequest
from generators.report_generator import conf_stanza, slug


@dataclass
class CorrelationSearchDefinition(Artifact):
    kind = "correlation"
    name: str
    title: str
    description: str
    spl: str
    cron: str
    earliest: str
    latest: str
    severity: Severity
    security_domain: str
    mitre: list[str] = field(default_factory=list)
    risk_object_field: str | None = None
    risk_object_type: str | None = None
    risk_score: int = 40
    drilldown_search: str = ""
    throttle_fields: list[str] = field(default_factory=list)
    suppress_period: str = "1h"

    def saved_search_params(self) -> dict[str, Any]:
        p: dict[str, Any] = {
            "search": self.spl, "description": self.description, "is_scheduled": "1", "cron_schedule": self.cron,
            "schedule_window": "auto", "dispatch.earliest_time": self.earliest, "dispatch.latest_time": self.latest,
            "alert_type": "number of events", "alert_comparator": "greater than", "alert_threshold": "0",
            "alert.track": "0", "action.correlationsearch.enabled": "1",
            "action.correlationsearch.label": self.title,
            "action.correlationsearch.annotations": json.dumps({"mitre_attack": self.mitre}),
            "action.notable": "1",
            "action.notable.param.rule_title": f"{self.title}" + (f" - ${self.risk_object_field}$" if self.risk_object_field else ""),
            "action.notable.param.rule_description": self.description,
            "action.notable.param.security_domain": self.security_domain,
            "action.notable.param.severity": self.severity.es_severity,
            "action.notable.param.drilldown_name": f"View contributing events for {self.title}",
            "action.notable.param.drilldown_search": self.drilldown_search,
        }
        actions = ["notable"]
        if self.risk_object_field:
            actions.append("risk")
            p.update({
                "action.risk": "1",
                "action.risk.param._risk": json.dumps([{"risk_object_field": self.risk_object_field,
                                                        "risk_object_type": self.risk_object_type or "other",
                                                        "risk_score": self.risk_score}]),
                "action.risk.param._risk_message": f"{self.title} observed for ${self.risk_object_field}$",
            })
        if self.throttle_fields:
            p.update({"alert.suppress": "1", "alert.suppress.fields": ",".join(self.throttle_fields),
                      "alert.suppress.period": self.suppress_period})
        p["actions"] = ",".join(actions)
        return p

    def to_conf(self) -> str:
        return conf_stanza(self.name, self.saved_search_params())

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "title": self.title, "spl": self.spl, "cron": self.cron,
                "severity": self.severity.es_severity, "security_domain": self.security_domain,
                "mitre_attack": self.mitre, "risk": {"field": self.risk_object_field, "type": self.risk_object_type,
                                                    "score": self.risk_score},
                "saved_search_params": self.saved_search_params()}

    def files(self) -> dict[str, str]:
        return {f"correlation_{slug(self.title)}.conf": self.to_conf()}

    def to_markdown(self) -> str:
        risk = (f"{self.risk_object_field} ({self.risk_object_type}) +{self.risk_score}"
                if self.risk_object_field else "none")
        return "\n".join([
            f"**Correlation search:** {self.title}",
            f"- Security domain: {self.security_domain} | Severity: {self.severity.es_severity}",
            f"- MITRE ATT&CK: {', '.join(self.mitre) or 'n/a'}",
            f"- Risk: {risk}",
            f"- Schedule: `{self.cron}` ({describe_cron(self.cron)})",
            "", "```spl", self.spl, "```", "", "```ini", self.to_conf().rstrip(), "```",
        ])


class CorrelationGenerator(ArtifactGenerator):
    name = "correlation"
    order = 30

    def applies(self, request: GenerationRequest) -> bool:
        if request.artifact_type is ArtifactType.CORRELATION:
            return True
        return request.artifact_type is ArtifactType.ALERT and request.use_case.correlation

    def generate(self, request: GenerationRequest) -> CorrelationSearchDefinition:
        uc = request.use_case
        explicit = request.artifact_type in (ArtifactType.ALERT, ArtifactType.CORRELATION)
        spec, search, m = build_alert_search(self.services, uc, request.intent, explicit=explicit)
        risk_field = search.datasource.field(uc.risk_object[0]) if uc.risk_object else None
        title = request.intent.title or uc.name
        prefix = self.services.settings.generation.name_prefix
        domain = uc.security_domain or {"security": "threat", "compliance": "audit"}.get(uc.domain, "threat")
        return CorrelationSearchDefinition(
            name=f"{prefix}{domain.title()} - {title} - Rule", title=title, description=uc.description, spl=m["spl"],
            cron=m["cron"], earliest=m["earliest"], latest=m["latest"], severity=m["severity"],
            security_domain=domain, mitre=list(uc.mitre), risk_object_field=risk_field,
            risk_object_type=uc.risk_object[1] if uc.risk_object else None, risk_score=uc.risk_score,
            drilldown_search=search.spl, throttle_fields=m["throttle"], suppress_period=spec.suppress_period)

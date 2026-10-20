"""Alert definitions: threshold SPL, schedule, severity, throttling, actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.models import AlertSpec, ArtifactType, Severity, UseCase, format_number
from core.schedule import describe_cron, window_schedule
from core.spl import quote_eval_field
from generators.base import Artifact, ArtifactGenerator, GenerationRequest
from generators.report_generator import conf_stanza, slug
from generators.search_generator import GeneratedSearch

_EXPLICIT = (ArtifactType.ALERT, ArtifactType.CORRELATION)
_DEFAULT_ACTIONS = ("Review the matching results and confirm the condition is genuine.",
                    "Identify the owning team / asset and notify them.",
                    "Document findings and tune the threshold if this is noise.")


@dataclass
class AlertDefinition:
    name: str
    title: str
    description: str
    use_case_id: str
    spl: str
    metric: str
    comparator: str
    threshold: float
    severity: Severity
    window: str
    cron: str
    earliest: str
    latest: str
    throttle_fields: list[str] = field(default_factory=list)
    suppress_period: str = "1h"
    recommended_actions: list[str] = field(default_factory=list)
    email_to: str | None = None
    webhook_url: str | None = None
    email_body: str = ""

    @property
    def condition(self) -> str:
        return f"{self.metric} {self.comparator} {format_number(self.threshold)}"

    def saved_search_params(self) -> dict[str, Any]:
        p: dict[str, Any] = {
            "search": self.spl, "description": self.description, "is_scheduled": "1",
            "cron_schedule": self.cron, "schedule_window": "auto",
            "dispatch.earliest_time": self.earliest, "dispatch.latest_time": self.latest,
            "alert_type": "number of events", "alert_comparator": "greater than", "alert_threshold": "0",
            "alert.track": "1", "alert.severity": str(self.severity.splunk_level), "alert.digest_mode": "1",
        }
        if self.throttle_fields:
            p.update({"alert.suppress": "1", "alert.suppress.fields": ",".join(self.throttle_fields),
                      "alert.suppress.period": self.suppress_period})
        actions = []
        if self.email_to:
            actions.append("email")
            p.update({"action.email.to": self.email_to, "action.email.subject": f"[{self.severity.value.upper()}] $name$",
                      "action.email.message.alert": self.email_body, "action.email.inline": "1",
                      "action.email.sendresults": "1"})
        if self.webhook_url:
            actions.append("webhook")
            p["action.webhook.param.url"] = self.webhook_url
        if actions:
            p["actions"] = ",".join(actions)
        return p

    def to_conf(self) -> str:
        return conf_stanza(self.name, self.saved_search_params())

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "title": self.title, "use_case": self.use_case_id, "spl": self.spl,
                "condition": self.condition, "threshold": self.threshold, "severity": self.severity.value,
                "window": self.window, "cron": self.cron, "schedule": describe_cron(self.cron),
                "time_range": {"earliest": self.earliest, "latest": self.latest},
                "throttle": {"fields": self.throttle_fields, "period": self.suppress_period},
                "recommended_actions": self.recommended_actions, "saved_search_params": self.saved_search_params()}

    def to_markdown(self) -> str:
        actions = "\n".join(f"  - {a}" for a in self.recommended_actions)
        throttle = f"{', '.join(self.throttle_fields)} for {self.suppress_period}" if self.throttle_fields else "none"
        return "\n".join([
            f"**Alert:** {self.title}",
            f"- Severity: **{self.severity.value.title()}** (alert.severity={self.severity.splunk_level})",
            f"- Threshold: `{self.condition}` evaluated over {self.window}",
            f"- Schedule: `{self.cron}` ({describe_cron(self.cron)}), window `{self.earliest}` to `{self.latest}`",
            f"- Throttle: {throttle}",
            "- Recommended actions:", actions, "", "```spl", self.spl, "```",
        ])


@dataclass
class AlertArtifact(Artifact):
    kind = "alert"
    title: str
    definitions: list[AlertDefinition]
    primary: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"primary": self.primary, "alerts": [d.to_dict() for d in self.definitions]}

    def files(self) -> dict[str, str]:
        if not self.definitions:
            return {}
        return {"alerts_savedsearches.conf": "\n".join(d.to_conf() for d in self.definitions)}

    def to_markdown(self) -> str:
        parts = [d.to_markdown() for d in self.definitions]
        if self.definitions:
            parts.append("savedsearches.conf:\n\n```ini\n" + "\n".join(d.to_conf() for d in self.definitions).rstrip() + "\n```")
        return "\n\n".join(parts)


def build_alert_search(services: Any, uc: UseCase, intent: Any, *, explicit: bool) -> tuple[AlertSpec, GeneratedSearch, dict]:
    """Shared by alert & correlation generators."""
    spec = uc.alert or AlertSpec(threshold=0, metric="count", pipeline="| stats count")
    window = (intent.window if explicit and intent.window else None) or (
        "1h" if explicit and intent.schedule == "0 * * * *" else None) or spec.window
    threshold = intent.threshold if explicit and intent.threshold is not None else spec.threshold
    comparator = intent.comparator if explicit and intent.comparator else spec.comparator
    severity = intent.severity if explicit and intent.severity else spec.severity
    span = intent.window if explicit and intent.window else None  # keep the rule's bucket span otherwise
    search = services.search_generator.generate(uc, intent, mode="alert", window=span, threshold=threshold,
                                                comparator=comparator)
    spl = search.spl
    if not search.has_threshold:
        spl += f"\n| where {quote_eval_field(spec.metric)} {comparator} {format_number(threshold)}"
    cron, earliest, latest = window_schedule(window)
    if spec.lookback:
        earliest, latest = spec.lookback, "now"
    throttle = [search.datasource.field(f) for f in spec.throttle_fields]
    meta = {"spl": spl, "window": window, "threshold": threshold, "comparator": comparator, "severity": severity,
            "cron": cron, "earliest": earliest, "latest": latest, "throttle": throttle}
    return spec, search, meta


class AlertGenerator(ArtifactGenerator):
    name = "alert"
    order = 20

    def applies(self, request: GenerationRequest) -> bool:
        return request.artifact_type in _EXPLICIT or any(u.alert for u in request.use_cases or [request.use_case])

    def _definition(self, uc: UseCase, request: GenerationRequest, explicit: bool) -> AlertDefinition:
        settings = self.services.settings.generation
        spec, _search, m = build_alert_search(self.services, uc, request.intent, explicit=explicit)
        title = request.intent.title if explicit and request.intent.title else uc.name
        actions = list(spec.recommended_actions or _DEFAULT_ACTIONS)
        body = self.services.templates.substitute(
            "alerts/email_body.txt", "$title fired ($condition). Severity: $severity.\n\n$actions",
            title=title, condition=f"{spec.metric} {m['comparator']} {format_number(m['threshold'])}",
            severity=m["severity"].value, description=uc.description,
            actions="\n".join(f"- {a}" for a in actions))
        return AlertDefinition(
            name=f"{settings.name_prefix}Alert - {title}", title=title, description=uc.description, use_case_id=uc.id,
            spl=m["spl"], metric=spec.metric, comparator=m["comparator"], threshold=m["threshold"],
            severity=m["severity"], window=m["window"], cron=m["cron"], earliest=m["earliest"], latest=m["latest"],
            throttle_fields=m["throttle"], suppress_period=spec.suppress_period, recommended_actions=actions,
            email_to=settings.alert_email_to, webhook_url=settings.alert_webhook_url, email_body=body)

    def generate(self, request: GenerationRequest) -> AlertArtifact:
        explicit = request.artifact_type in _EXPLICIT
        if request.artifact_type is ArtifactType.DASHBOARD:
            ucs = [u for u in dict.fromkeys(request.use_cases) if u.alert][:5]
        else:
            ucs = [request.use_case] if (explicit or request.use_case.alert) else []
        defs = [self._definition(u, request, explicit) for u in ucs]
        return AlertArtifact(title=request.title, definitions=defs, primary=explicit)

    @staticmethod
    def file_name(defn: AlertDefinition) -> str:
        return f"alert_{slug(defn.title)}.conf"

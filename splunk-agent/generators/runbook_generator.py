"""Operational runbooks (Markdown) built from use-case metadata and investigation searches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.models import ArtifactType, RunbookSpec, UseCase
from core.schedule import describe_cron
from generators.alert_generator import build_alert_search
from generators.base import Artifact, ArtifactGenerator, GenerationRequest
from generators.report_generator import slug

DEFAULT_RUNBOOKS: dict[str, RunbookSpec] = {
    "security": RunbookSpec(
        triage=("Validate the detection is not a known benign activity (scanner, pentest, admin task).",
                "Identify affected users/assets and their criticality."),
        remediation=("Contain: disable account / isolate host / block indicator as appropriate.",
                     "Eradicate and recover; document the timeline in the incident ticket."),
        escalation="Escalate to the SOC lead for any confirmed compromise."),
    "kubernetes": RunbookSpec(
        triage=("Identify cluster, namespace and workload owner.", "Check recent deployments: kubectl rollout history."),
        remediation=("kubectl describe / kubectl logs --previous for the affected pods.",
                     "Roll back or scale as needed."),
        escalation="Page the platform on-call if multiple namespaces are affected."),
    "infrastructure": RunbookSpec(
        triage=("Identify affected hosts and services.",),
        remediation=("Log in to the host and validate resource usage / service status (systemctl, journalctl).",),
        escalation="Escalate to the infrastructure on-call if production capacity is at risk."),
    "default": RunbookSpec(
        triage=("Confirm the condition and its business impact.",),
        remediation=("Apply the documented fix or roll back the triggering change.",),
        escalation="Escalate to the owning team."),
}


@dataclass
class RunbookDocument(Artifact):
    kind = "runbook"
    title: str
    markdown: str

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "markdown": self.markdown}

    def files(self) -> dict[str, str]:
        return {f"runbook_{slug(self.title)}.md": self.markdown}

    def to_markdown(self) -> str:
        return f"Runbook written to `runbook_{slug(self.title)}.md`.\n\n" + self.markdown


def _bullets(items: tuple[str, ...] | list[str], numbered: bool = False) -> str:
    if not items:
        return "- n/a"
    return "\n".join((f"{i}. " if numbered else "- ") + it for i, it in enumerate(items, 1))


class RunbookGenerator(ArtifactGenerator):
    name = "runbook"
    order = 50

    def applies(self, request: GenerationRequest) -> bool:
        return request.artifact_type in (ArtifactType.RUNBOOK, ArtifactType.ALERT, ArtifactType.CORRELATION)

    def _investigations(self, uc: UseCase, request: GenerationRequest, spec: RunbookSpec) -> str:
        sg = self.services.search_generator
        blocks = []
        for item in spec.investigation:
            try:
                if item.startswith("uc:"):
                    other = self.services.registry.use_cases.get(item[3:])
                    if not other:
                        continue
                    blocks.append(f"**{other.name}**\n\n```spl\n{sg.generate(other, request.intent).adhoc_spl}\n```")
                else:
                    blocks.append(f"```spl\n{sg.render_snippet(uc, item, request.intent)}\n```")
            except Exception as exc:  # noqa: BLE001 - a failing snippet must not block the runbook
                blocks.append(f"_Investigation search unavailable: {exc}_")
        return "\n\n".join(blocks) or "_No additional investigation searches defined._"

    def generate(self, request: GenerationRequest) -> RunbookDocument:
        uc = request.use_case
        spec = uc.runbook or DEFAULT_RUNBOOKS.get(uc.domain, DEFAULT_RUNBOOKS["default"])
        alert_spec, _search, m = build_alert_search(self.services, uc, request.intent,
                                                    explicit=request.artifact_type is not ArtifactType.RUNBOOK)
        title = f"{uc.name} Runbook"
        values = {
            "title": title, "name": uc.name, "description": uc.description, "domain": uc.domain,
            "business_value": uc.business_value or uc.description,
            "severity": m["severity"].value.title(),
            "condition": f"{alert_spec.metric} {m['comparator']} {m['threshold']:g}",
            "schedule": f"{m['cron']} ({describe_cron(m['cron'])})", "window": m["window"],
            "spl": m["spl"], "triage": _bullets(spec.triage, numbered=True),
            "investigation": self._investigations(uc, request, spec),
            "remediation": _bullets(spec.remediation, numbered=True),
            "actions": _bullets(list(alert_spec.recommended_actions)),
            "escalation": spec.escalation or "Escalate to the owning team.",
            "mitre": ", ".join(uc.mitre) or "n/a",
            "references": _bullets(spec.references),
        }
        md = self.services.templates.substitute("runbooks/runbook.md", _FALLBACK, **values)
        return RunbookDocument(title=title, markdown=md)


_FALLBACK = """# $title

$description

## Detection
- Severity: $severity
- Condition: `$condition` over $window
- Schedule: $schedule

```spl
$spl
```

## Triage
$triage

## Investigation
$investigation

## Remediation
$remediation

## Escalation
$escalation
"""

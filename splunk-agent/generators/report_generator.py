"""Scheduled report / saved search definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.models import ArtifactType, Visualization
from core.schedule import describe_cron
from core.visualization import recommend
from generators.base import Artifact, ArtifactGenerator, GenerationRequest


# A scheduled report covers exactly one schedule interval (no gaps, no overlap).
_SCHEDULE_RANGES = {
    "0 * * * *": ("-1h@h", "@h"),
    "0 1 * * *": ("-1d@d", "@d"),
    "0 6 * * *": ("-1d@d", "@d"),
    "0 7 * * 1": ("-7d@d", "@d"),
    "0 7 1 * *": ("-1mon@mon", "@mon"),
}


def conf_stanza(name: str, params: dict[str, Any]) -> str:
    """Render a savedsearches.conf stanza (multi-line values use backslash continuation)."""
    lines = [f"[{name}]"]
    for key in sorted(params):
        value = str(params[key])
        if "\n" in value:
            value = " \\\n".join(value.splitlines())
        lines.append(f"{key} = {value}")
    return "\n".join(lines) + "\n"


def slug(text: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "_" for ch in text)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")[:80] or "artifact"


@dataclass
class ReportDefinition(Artifact):
    kind = "report"
    name: str
    title: str
    description: str
    business_description: str
    spl: str
    cron: str
    earliest: str
    latest: str
    visualization: Visualization
    scheduled: bool = True
    display: dict[str, str] = field(default_factory=dict)

    @property
    def schedule_text(self) -> str:
        return describe_cron(self.cron) if self.scheduled else "not scheduled (run on demand)"

    def saved_search_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "search": self.spl, "description": self.description,
            "dispatch.earliest_time": self.earliest, "dispatch.latest_time": self.latest,
            "is_scheduled": "1" if self.scheduled else "0", "request.ui_dispatch_app": "search",
            "request.ui_dispatch_view": "search", **self.display,
        }
        if self.scheduled:
            params.update({"cron_schedule": self.cron, "schedule_window": "auto"})
        return params

    def to_conf(self) -> str:
        return conf_stanza(self.name, self.saved_search_params())

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "title": self.title, "description": self.description,
                "business_description": self.business_description, "spl": self.spl,
                "schedule": {"cron": self.cron if self.scheduled else None, "human": self.schedule_text},
                "time_range": {"earliest": self.earliest, "latest": self.latest},
                "visualization": self.visualization.value, "saved_search_params": self.saved_search_params()}

    def files(self) -> dict[str, str]:
        return {f"report_{slug(self.title)}.conf": self.to_conf()}

    def to_markdown(self) -> str:
        return "\n".join([
            f"**Report:** {self.title}",
            f"**Description:** {self.business_description}",
            f"**Schedule:** `{self.cron}` ({self.schedule_text})" if self.scheduled else f"**Schedule:** {self.schedule_text}",
            f"**Time range:** `{self.earliest}` to `{self.latest}`",
            f"**Visualization:** {self.visualization.value}",
            "", "```spl", self.spl, "```", "", "savedsearches.conf:", "", "```ini", self.to_conf().rstrip(), "```",
        ])


class ReportGenerator(ArtifactGenerator):
    name = "report"
    order = 10

    def applies(self, request: GenerationRequest) -> bool:
        return True

    def generate(self, request: GenerationRequest) -> ReportDefinition:
        uc, search, intent = request.use_case, request.search, request.intent
        settings = self.services.settings.generation
        scheduled = intent.artifact_type is not ArtifactType.SAVED_SEARCH or bool(intent.schedule)
        cron = intent.schedule or uc.report_cron
        title = intent.title if intent.title and intent.artifact_type in (
            ArtifactType.REPORT, ArtifactType.SAVED_SEARCH) else uc.name
        templates = self.services.templates.yaml("reports/descriptions.yaml", {}) or {}
        business = uc.business_value or templates.get(uc.domain) or templates.get("default") or uc.description
        business = business.replace("$name", uc.name).replace("$description", uc.description)
        viz = recommend(search.spl, uc.visualization).primary
        earliest, latest = search.earliest, search.latest
        if intent.schedule and not intent.time_range:
            earliest, latest = _SCHEDULE_RANGES.get(intent.schedule, (earliest, latest))
        return ReportDefinition(
            name=f"{settings.name_prefix}Report - {title}", title=title, description=uc.description,
            business_description=business, spl=search.spl, cron=cron, earliest=earliest,
            latest=latest, visualization=viz, scheduled=scheduled, display=viz.saved_search_display())

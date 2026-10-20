"""Agent response object + Markdown/JSON rendering and file output."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.intent import Intent
from core.models import ArtifactType, UseCase
from core.visualization import VisualizationRecommendation

if TYPE_CHECKING:  # pragma: no cover
    from generators.base import Artifact
    from generators.dashboard_generator import DashboardComponent
    from generators.search_generator import GeneratedSearch


@dataclass
class AgentResponse:
    request: str
    intent: Intent
    title: str
    use_cases: list[UseCase]
    searches: list["GeneratedSearch"]
    explanation: list[str]
    visualization: VisualizationRecommendation
    components: list["DashboardComponent"]
    artifacts: dict[str, "Artifact"] = field(default_factory=dict)
    confidence: float = 0.0
    alternatives: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def artifact_type(self) -> ArtifactType:
        return self.intent.artifact_type

    @property
    def primary_search(self) -> "GeneratedSearch":
        return self.searches[0]

    def artifact(self, kind: str) -> Any:
        return self.artifacts.get(kind)

    # ------------------------------------------------------------- output
    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "title": self.title,
            "artifact_type": self.artifact_type.value,
            "confidence": self.confidence,
            "intent": self.intent.to_dict(),
            "use_cases": [uc.id for uc in self.use_cases],
            "alternatives": self.alternatives,
            "generated_spl": [s.to_dict() for s in self.searches],
            "explanation": self.explanation,
            "visualization": self.visualization.to_dict(),
            "dashboard_components": [c.to_dict() for c in self.components],
            "artifacts": {k: a.to_dict() for k, a in self.artifacts.items()},
            "warnings": self.warnings,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    def to_markdown(self) -> str:
        s = self.primary_search
        intent = self.intent
        meta = [f"- **Request:** {self.request}",
                f"- **Artifact:** {self.artifact_type.value}  |  **Matched:** "
                f"{', '.join(dict.fromkeys(u.id for u in self.use_cases))}  |  **Confidence:** {self.confidence:.0%}"]
        if intent.time_range:
            meta.append(f"- **Time range:** {intent.time_range.earliest} to {intent.time_range.latest}")
        if intent.threshold is not None:
            meta.append(f"- **Threshold:** {intent.comparator} {intent.threshold:g}"
                        + (f" per {intent.window}" if intent.window else ""))
        if self.alternatives:
            meta.append(f"- **Other candidates:** {', '.join(self.alternatives)}")
        out = [f"# {self.title}", "", *meta, "", "## 1. Generated SPL", ""]
        out += ["Ad-hoc (inline time range):", "", "```spl", s.adhoc_spl, "```", "",
                "Saved-search form (time range set by schedule/dispatch):", "", "```spl", s.spl, "```"]
        if s.accelerated_spl:
            out += ["", "Accelerated (tstats on CIM data model):", "", "```spl", s.accelerated_spl, "```"]
        if len(self.searches) > 1:
            out += ["", f"_{len(self.searches) - 1} panel searches are included in the dashboard "
                        "definition and JSON output._"]
        out += ["", "## 2. Explanation", "", *[f"- {line}" for line in self.explanation]]
        v = self.visualization
        out += ["", "## 3. Visualization Recommendation", "",
                f"- **Primary:** {v.primary.value} (`{v.studio_type}`)", f"- **Why:** {v.rationale}"]
        if v.alternatives:
            out.append(f"- **Alternatives:** {', '.join(a.value for a in v.alternatives)}")
        out += ["", "## 4. Dashboard Component Suggestions", "", "| Panel | Kind | Studio type | Use case |",
                "|---|---|---|---|"]
        out += [f"| {c.title} | {c.kind} | `{c.visualization.studio_type}` | {c.use_case_id} |" for c in self.components]
        alert = self.artifacts.get("alert")
        out += ["", "## 5. Alert Recommendations", ""]
        out.append(alert.to_markdown() if alert and alert.definitions else "_No alert recommended for this use case._")
        report = self.artifacts.get("report")
        out += ["", "## 6. Report Definition", "", report.to_markdown() if report else "_n/a_"]
        extra = [(k, a) for k, a in self.artifacts.items() if k not in ("alert", "report")]
        for kind, art in extra:
            out += ["", f"## {kind.replace('_', ' ').title()}", "", art.to_markdown()]
        if self.warnings:
            out += ["", "## Warnings", "", *[f"- {w}" for w in dict.fromkeys(self.warnings)]]
        return "\n".join(out) + "\n"

    def write(self, out_dir: str | Path) -> list[Path]:
        d = Path(out_dir)
        d.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []

        def put(name: str, content: str) -> None:
            p = d / name
            p.write_text(content, encoding="utf-8")
            written.append(p)

        put("response.md", self.to_markdown())
        put("response.json", self.to_json())
        put("search.spl", self.primary_search.adhoc_spl + "\n")
        for art in self.artifacts.values():
            for name, content in art.files().items():
                put(name, content)
        return written

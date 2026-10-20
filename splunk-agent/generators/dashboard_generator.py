"""Dashboard Studio (version 2) JSON generation with KPIs, charts, tables, trends and drilldowns."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from xml.sax.saxutils import escape

from core.intent import Intent
from core.models import ArtifactType, DashboardBlueprint, InputSpec, PanelSpec, UseCase, Visualization
from core.visualization import recommend
from generators.base import Artifact, ArtifactGenerator, GenerationRequest
from generators.report_generator import slug
from generators.search_generator import GeneratedSearch, SearchGenerator

log = logging.getLogger(__name__)

CANVAS_WIDTH = 1440
KPI_H, CHART_H, TABLE_H, GAP = 120, 320, 360, 10


@dataclass
class DashboardComponent:
    title: str
    kind: str  # kpi | chart | table
    visualization: Visualization
    spl: str
    use_case_id: str
    description: str = ""
    drilldown: str = "linkToSearch"
    search: GeneratedSearch | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "kind": self.kind, "visualization": self.visualization.value,
                "studio_type": self.visualization.studio_type, "use_case": self.use_case_id,
                "description": self.description, "drilldown": self.drilldown, "spl": self.spl}


class DashboardComposer:
    """Builds dashboard components from use cases (shared by agent + generator plugin)."""

    def __init__(self, search_generator: SearchGenerator, registry: Any, max_panels: int = 16) -> None:
        self.search_generator = search_generator
        self.registry = registry
        self.max_panels = max_panels

    def component(self, uc: UseCase, intent: Intent | None, panel: PanelSpec | None = None,
                  inputs: tuple[InputSpec, ...] = ()) -> DashboardComponent:
        panel = panel or PanelSpec(uc.id)
        viz = panel.visualization or uc.visualization
        mode = "single" if viz is Visualization.SINGLE and panel.pipeline is None else "search"
        extra = {}
        for inp in inputs:
            if inp.field in uc.required_fields or (uc.kind == "raw" and "extra_filter" in uc.placeholders):
                extra[inp.field] = f"${inp.token}$"
        search = self.search_generator.generate(uc, intent, mode=mode, pipeline_override=panel.pipeline,
                                                extra_filters=extra)
        if panel.visualization is None:
            viz = recommend(search.spl, uc.visualization).primary
        title = panel.title or (uc.name if viz is not Visualization.SINGLE else f"{uc.name} (total)")
        return DashboardComponent(title, viz.panel_kind, viz, search.spl, uc.id,
                                  panel.description or uc.description, search=search)

    def suggest(self, uc: UseCase, intent: Intent) -> list[DashboardComponent]:
        """Component suggestions for a single-use-case request."""
        out = [self.component(uc, intent, PanelSpec(uc.id, f"{uc.name} (total)", Visualization.SINGLE)),
               self.component(uc, intent)]
        if uc.visualization is not Visualization.LINE and uc.kind == "events":
            out.append(self.component(uc, intent, PanelSpec(
                uc.id, f"{uc.name} - Trend", Visualization.LINE, pipeline="| timechart span={{span}} count")))
        for rel in uc.related[:3]:
            if rel in self.registry.use_cases:
                out.append(self.component(self.registry.use_cases[rel], intent))
        return out

    def from_blueprint(self, bp: DashboardBlueprint, intent: Intent) -> list[DashboardComponent]:
        comps = []
        for panel in bp.panels[: self.max_panels]:
            try:
                comps.append(self.component(self.registry.use_cases[panel.use_case], intent, panel, bp.inputs))
            except Exception as exc:  # noqa: BLE001 - skip a broken panel, keep the dashboard
                log.warning("Skipping panel %s: %s", panel.use_case, exc)
        return comps

    def auto(self, use_cases: list[UseCase], intent: Intent) -> list[DashboardComponent]:
        """Compose a dashboard when no blueprint matches: KPIs first, then each use case's main panel."""
        comps = [self.component(uc, intent, PanelSpec(uc.id, uc.name, Visualization.SINGLE))
                 for uc in use_cases[:4]]
        comps += [self.component(uc, intent) for uc in use_cases]
        return comps[: self.max_panels]


@dataclass
class DashboardDefinition(Artifact):
    kind = "dashboard"
    name: str
    title: str
    description: str
    definition: dict[str, Any]
    components: list[DashboardComponent]
    theme: str = "dark"

    def to_xml(self) -> str:
        payload = json.dumps(self.definition, indent=2).replace("]]>", "]]]]><![CDATA[>")
        return (f'<dashboard version="2" theme="{self.theme}">\n'
                f"    <label>{escape(self.title)}</label>\n"
                f"    <description>{escape(self.description)}</description>\n"
                f"    <definition><![CDATA[\n{payload}\n]]></definition>\n"
                '    <meta type="hiddenElements"><![CDATA[\n{"hideEdit": false, "hideOpenInSearch": false, '
                '"hideExport": false}\n]]></meta>\n</dashboard>\n')

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "title": self.title, "panels": [c.to_dict() for c in self.components],
                "definition": self.definition}

    def files(self) -> dict[str, str]:
        return {f"dashboard_{self.name}.json": json.dumps(self.definition, indent=2),
                f"dashboard_{self.name}.xml": self.to_xml()}

    def to_markdown(self) -> str:
        rows = "\n".join(f"| {c.title} | {c.kind} | `{c.visualization.studio_type}` | {c.use_case_id} |"
                         for c in self.components)
        return (f"**Dashboard Studio:** {self.title} (`{self.name}`), {len(self.components)} panels, "
                f"global time picker + drilldowns.\n\n| Panel | Kind | Type | Use case |\n|---|---|---|---|\n{rows}\n\n"
                "Full definition written to `dashboard_<name>.json` (Studio source) and `.xml` (deployable view).")


def _viz_options(viz: Visualization, search: GeneratedSearch | None) -> dict[str, Any]:
    if viz is Visualization.SINGLE:
        return {"majorValueSize": 36, "trendDisplay": "off", "sparklineDisplay": "off"}
    if viz is Visualization.TABLE:
        return {"count": 10}
    if viz in (Visualization.COLUMN, Visualization.BAR):
        return {"legendDisplay": "off", "dataValuesDisplay": "off"}
    if viz in (Visualization.LINE, Visualization.AREA):
        return {"legendDisplay": "right", "nullValueDisplay": "zero"}
    return {}


def build_definition(title: str, description: str, components: list[DashboardComponent],
                     inputs: tuple[InputSpec, ...] = (), *, default_time: str = "-24h@h,now",
                     base_template: dict[str, Any] | None = None) -> dict[str, Any]:
    data_sources: dict[str, Any] = {}
    visualizations: dict[str, Any] = {}
    structure: list[dict[str, Any]] = []
    used: set[str] = set()

    def unique(prefix: str, text: str) -> str:
        key, n = f"{prefix}_{slug(text)[:40]}", 1
        while key in used:
            n += 1
            key = f"{prefix}_{slug(text)[:40]}_{n}"
        used.add(key)
        return key

    ordered = ([c for c in components if c.kind == "kpi"] + [c for c in components if c.kind == "chart"]
               + [c for c in components if c.kind == "table"])
    y = 0
    kpis = [c for c in ordered if c.kind == "kpi"]
    charts = [c for c in ordered if c.kind == "chart"]
    tables = [c for c in ordered if c.kind == "table"]

    def add(comp: DashboardComponent, x: int, y: int, w: int, h: int) -> None:
        ds_id, viz_id = unique("ds", comp.title), unique("viz", comp.title)
        data_sources[ds_id] = {"type": "ds.search", "name": comp.title,
                               "options": {"query": comp.spl, "enableSmartSources": True}}
        visualizations[viz_id] = {
            "type": comp.visualization.studio_type, "title": comp.title, "description": comp.description,
            "dataSources": {"primary": ds_id}, "options": _viz_options(comp.visualization, comp.search),
            "eventHandlers": [{"type": "drilldown.linkToSearch", "options": {"type": "auto", "newTab": True}}],
        }
        structure.append({"item": viz_id, "type": "block", "position": {"x": x, "y": y, "w": w, "h": h}})

    for row_start in range(0, len(kpis), 4):
        row = kpis[row_start:row_start + 4]
        w = CANVAS_WIDTH // len(row)
        for i, comp in enumerate(row):
            add(comp, i * w, y, w - (GAP if i < len(row) - 1 else 0), KPI_H)
        y += KPI_H + GAP
    for row_start in range(0, len(charts), 2):
        row = charts[row_start:row_start + 2]
        w = CANVAS_WIDTH // len(row)
        for i, comp in enumerate(row):
            add(comp, i * w, y, w - (GAP if i < len(row) - 1 else 0), CHART_H)
        y += CHART_H + GAP
    for comp in tables:
        add(comp, 0, y, CANVAS_WIDTH, TABLE_H)
        y += TABLE_H + GAP

    dash_inputs: dict[str, Any] = {
        "input_global_trp": {"type": "input.timerange", "title": "Time Range",
                             "options": {"token": "global_time", "defaultValue": default_time}},
    }
    for inp in inputs:
        dash_inputs[f"input_{inp.token}"] = {"type": "input.text", "title": inp.label,
                                             "options": {"token": inp.token, "defaultValue": inp.default}}
    definition: dict[str, Any] = dict(base_template or {})
    definition.update({
        "title": title,
        "description": description,
        "inputs": dash_inputs,
        "defaults": {"dataSources": {"ds.search": {"options": {"queryParameters": {
            "earliest": "$global_time.earliest$", "latest": "$global_time.latest$"}}}}},
        "visualizations": visualizations,
        "dataSources": data_sources,
        "layout": {"type": "absolute",
                   "options": {"width": CANVAS_WIDTH, "height": max(y, 400), "display": "auto-scale"},
                   "structure": structure, "globalInputs": list(dash_inputs)},
    })
    return definition


class DashboardGenerator(ArtifactGenerator):
    name = "dashboard"
    order = 40

    def applies(self, request: GenerationRequest) -> bool:
        return request.artifact_type is ArtifactType.DASHBOARD and bool(request.components)

    def generate(self, request: GenerationRequest) -> DashboardDefinition:
        bp = request.blueprint
        title = request.intent.title or (bp.title if bp else request.title)
        description = bp.description if bp else f"Auto-generated from request: {request.intent.text}"
        settings = self.services.settings.generation
        base = self.services.templates.json("dashboards/base.json", {}) or {}
        default_time = base.pop("defaultTime", "-24h@h,now") if isinstance(base, dict) else "-24h@h,now"
        definition = build_definition(title, description, request.components, bp.inputs if bp else (),
                                      default_time=default_time, base_template=base)
        return DashboardDefinition(name=slug(f"auto_{title}"), title=title, description=description,
                                   definition=definition, components=request.components,
                                   theme=settings.dashboard_theme)

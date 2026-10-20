"""Rule-based visualization recommendation from the *shape* of an SPL result."""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.models import Visualization
from core.spl import command_of, split_pipes

_TRANSFORMING = {"stats", "timechart", "chart", "top", "rare", "tstats", "mstats", "table"}


@dataclass(frozen=True)
class VisualizationRecommendation:
    primary: Visualization
    rationale: str
    alternatives: tuple[Visualization, ...] = ()

    @property
    def studio_type(self) -> str:
        return self.primary.studio_type

    def to_dict(self) -> dict:
        return {"primary": self.primary.value, "studio_type": self.studio_type, "rationale": self.rationale,
                "alternatives": [a.value for a in self.alternatives]}


def _by_fields(stage: str) -> list[str]:
    parts = re.split(r"\bby\b", stage, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) < 2:
        return []
    clause = re.sub(r"\b(span|limit|useother)=\S+", "", parts[1])
    return [f for f in re.split(r"[\s,]+", clause) if f]


def infer(spl: str) -> tuple[Visualization, str, tuple[Visualization, ...]]:
    stages = [s.strip() for s in split_pipes(spl) if s.strip()]
    last = None
    for stage in stages:
        if command_of(stage) in _TRANSFORMING:
            last = stage
    if last is None:
        return Visualization.EVENTS, "No transforming command - raw events list.", (Visualization.TABLE,)
    cmd = command_of(last)
    if cmd == "timechart":
        return (Visualization.LINE, "Time-bucketed series are best read as a trend line.",
                (Visualization.AREA, Visualization.COLUMN))
    if cmd in ("top", "rare"):
        return Visualization.BAR, "Ranked frequency list suits a bar chart.", (Visualization.TABLE, Visualization.PIE)
    if cmd == "table":
        return Visualization.TABLE, "Explicit column list - tabular output.", ()
    by = _by_fields(last)
    if "_time" in by:
        return (Visualization.LINE, "Results are split by _time - trend over time.", (Visualization.COLUMN,))
    if not by:
        return Visualization.SINGLE, "Single aggregate value - KPI single-value tile.", (Visualization.TABLE,)
    aggs = len(re.findall(r"\w+\([^)]*\)", last.split(" by ")[0].split(" BY ")[0])) or 1
    if len(by) == 1 and aggs <= 1:
        return (Visualization.COLUMN, "One category with one measure - ranked column chart.",
                (Visualization.BAR, Visualization.PIE, Visualization.TABLE))
    return (Visualization.TABLE, f"{len(by)} dimension(s) and {aggs} measure(s) - a table preserves detail.",
            (Visualization.COLUMN,))


def recommend(spl: str, declared: Visualization | None = None) -> VisualizationRecommendation:
    inferred, rationale, alternatives = infer(spl)
    if declared and declared != inferred:
        alts = tuple(dict.fromkeys((inferred, *alternatives)))
        alts = tuple(a for a in alts if a != declared)
        return VisualizationRecommendation(declared, f"Rule pack recommends {declared.value}. Shape analysis: {rationale}", alts)
    return VisualizationRecommendation(inferred, rationale, tuple(a for a in alternatives if a != inferred))

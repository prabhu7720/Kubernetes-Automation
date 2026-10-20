"""Natural-language-to-SPL engine: renders a use case against the resolved datasource."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from catalog.enrichment import EnrichmentResolver
from catalog.resolver import DataSourceResolver, ResolvedDataSource
from core.config import GenerationSettings
from core.exceptions import TemplateRenderError, ValidationError
from core.intent import FieldFilter, Intent
from core.models import UseCase, format_number
from core.spl import LintIssue, lint, quote_eval_field, quote_value
from core.spl_explainer import explain
from core.template import placeholders, render

log = logging.getLogger(__name__)
_MULTISPACE = re.compile(r"(?<=\S)[ \t]{2,}")


@dataclass
class GeneratedSearch:
    use_case_id: str
    title: str
    spl: str
    adhoc_spl: str
    earliest: str
    latest: str
    span: str
    limit: int
    groupby: str | None
    threshold: float
    comparator: str
    has_threshold: bool
    datasource: ResolvedDataSource
    accelerated_spl: str | None = None
    explanation: list[str] = field(default_factory=list)
    lint: list[LintIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "use_case": self.use_case_id, "title": self.title, "spl": self.spl, "adhoc_spl": self.adhoc_spl,
            "accelerated_spl": self.accelerated_spl, "earliest": self.earliest, "latest": self.latest,
            "span": self.span, "limit": self.limit, "groupby": self.groupby,
            "datasource": self.datasource.to_dict(), "explanation": self.explanation,
            "lint": [i.to_dict() for i in self.lint], "warnings": self.warnings,
        }


class _Context:
    """Placeholder resolver for one rendering pass."""

    def __init__(self, uc: UseCase, resolved: ResolvedDataSource, enrich: EnrichmentResolver, *,
                 params: dict[str, Any], groupby: str | None, threshold: float, comparator: str, span: str,
                 limit: int, extra_filter: str, time_clause: str) -> None:
        self.uc, self.resolved, self.enrich = uc, resolved, enrich
        self.params, self.groupby, self.threshold, self.comparator = params, groupby, threshold, comparator
        self.span, self.limit, self.extra_filter, self.time_clause = span, limit, extra_filter, time_clause

    def __call__(self, key: str) -> str:
        simple = {
            "base": lambda: self.resolved.base, "index": lambda: self.resolved.index_clause,
            "time": lambda: self.time_clause, "extra_filter": lambda: self.extra_filter,
            "threshold": lambda: format_number(self.threshold), "comparator": lambda: self.comparator,
            "span": lambda: self.span, "limit": lambda: str(self.limit),
        }
        if key in simple:
            return simple[key]()
        if key in ("groupby", "qgroupby"):
            if not self.groupby:
                raise TemplateRenderError(f"{self.uc.id}: template uses {{{{groupby}}}} but no groupby is set")
            actual = self.resolved.field(self.groupby)
            return quote_eval_field(actual) if key == "qgroupby" else actual
        prefix, _, name = key.partition(".")
        if prefix == "f":
            return self.resolved.field(name)
        if prefix == "q":
            return quote_eval_field(self.resolved.field(name))
        if prefix == "m":
            return self.resolved.metric(name)
        if prefix == "p":
            if name not in self.params:
                raise TemplateRenderError(f"{self.uc.id}: unknown parameter '{name}'")
            value = self.params[name]
            return ", ".join(str(v) for v in value) if isinstance(value, (list, tuple)) else str(value)
        if prefix == "enrich":
            return self.enrich.clause(name, self.resolved.field)
        raise TemplateRenderError(f"{self.uc.id}: unknown placeholder '{{{{{key}}}}}'")


def _clean(spl: str) -> str:
    lines = []
    for line in spl.splitlines():
        line = _MULTISPACE.sub(" ", line.strip())
        if line and line != "|":
            lines.append(line)
    return "\n".join(lines)


class SearchGenerator:
    def __init__(self, resolver: DataSourceResolver, enrichments: EnrichmentResolver,
                 settings: GenerationSettings) -> None:
        self.resolver = resolver
        self.enrichments = enrichments
        self.settings = settings

    # --------------------------------------------------------------- public
    def generate(self, uc: UseCase, intent: Intent | None = None, *, mode: str = "search",
                 pipeline_override: str | None = None, extra_filters: dict[str, str] | None = None,
                 window: str | None = None, threshold: float | None = None, comparator: str | None = None,
                 earliest: str | None = None, latest: str | None = None) -> GeneratedSearch:
        """Render *uc*.

        mode: ``search`` (default pipeline), ``alert`` (alert pipeline), ``single`` (KPI pipeline).
        extra_filters: canonical field -> raw value (dashboard tokens such as ``$namespace$``).
        """
        template = self._pipeline_template(uc, mode, pipeline_override)
        filters = list(intent.field_filters) if intent else []
        filters += [FieldFilter(k, v) for k, v in (extra_filters or {}).items()]

        groupby = uc.groupby
        if intent and intent.groupby and (uc.uses_groupby or "groupby" in placeholders(template)):
            groupby = intent.groupby
        fields = set(uc.required_fields) | {f.field for f in filters}
        fields |= {p.split(".", 1)[1] for p in placeholders(template) if p.startswith(("f.", "q."))}
        if groupby:
            fields.add(groupby)
        metrics = set(uc.required_metrics) | {p.split(".", 1)[1] for p in placeholders(template) if p.startswith("m.")}

        resolved = self.resolver.resolve(
            uc.datasource, fields, metrics,
            pinned_indexes=intent.index_filters if intent else None,
            pinned_sourcetypes=intent.sourcetype_filters if intent else None)

        params = dict(uc.params)
        if intent and intent.status_codes and "status" in params:
            params["status"] = intent.status_codes
        span = window or (intent.window if intent and intent.window else uc.default_span)
        limit = (intent.limit if intent and intent.limit else uc.default_limit)
        alert = uc.alert
        thr = threshold if threshold is not None else (
            intent.threshold if intent and intent.threshold is not None else (alert.threshold if alert else 0))
        cmp_ = comparator or (intent.comparator if intent and intent.comparator else (alert.comparator if alert else ">"))
        tr = intent.time_range if intent else None
        e = earliest or (tr.earliest if tr else uc.default_earliest)
        l = latest or (tr.latest if tr else "now")

        extra = " ".join(f"{resolved.field(f.field)}{f.op}{quote_value(f.value)}" for f in filters)

        def ctx(time_clause: str) -> _Context:
            return _Context(uc, resolved, self.enrichments, params=params, groupby=groupby, threshold=thr,
                            comparator=cmp_, span=span, limit=limit, extra_filter=extra, time_clause=time_clause)

        inline_time = f"earliest={e} latest={l}"
        spl = self._assemble(uc, template, ctx(""), resolved, extra, time_inline=None)
        adhoc = self._assemble(uc, template, ctx(inline_time), resolved, extra, time_inline=inline_time)

        accelerated = None
        if (uc.tstats and resolved.datamodel_accelerated and self.settings.include_accelerated
                and mode == "search" and pipeline_override is None and not filters):
            accelerated = _clean(render(uc.tstats, ctx(inline_time)))

        issues = lint(adhoc)
        errors = [i for i in issues if i.level == "error"]
        if errors and self.settings.strict_lint:
            raise ValidationError(f"{uc.id}: generated SPL failed lint: {'; '.join(i.message for i in errors)}")

        explanation = [f"Use case '{uc.name}': {uc.description}", resolved.describe()]
        if resolved.normalization:
            explanation.append("Field names differ between the selected sourcetypes, so the search normalises them "
                               f"with `{resolved.normalization_eval}`.")
        explanation += explain(adhoc)
        if accelerated:
            explanation.append(f"The '{resolved.datamodel}' data model is accelerated - the tstats variant returns "
                               "the same answer far faster.")
        warnings = list(resolved.warnings) + [f"SPL {i.level}: {i.message}" for i in issues if i.level != "info"]
        return GeneratedSearch(uc.id, uc.name, spl, adhoc, e, l, span, limit, groupby, thr, cmp_,
                               "threshold" in placeholders(template), resolved, accelerated, explanation, issues,
                               warnings)

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _pipeline_template(uc: UseCase, mode: str, override: str | None) -> str:
        if override is not None:
            return override
        if mode == "alert" and uc.alert and uc.alert.pipeline:
            return uc.alert.pipeline
        if mode == "single":
            if uc.single_value:
                return uc.single_value
            return (uc.pipeline + "\n| stats count AS results") if uc.kind == "raw" else "| stats count"
        return uc.pipeline

    @staticmethod
    def _is_full_search(uc: UseCase, template: str) -> bool:
        return uc.kind == "raw" or template.lstrip().startswith("| tstats") or template.lstrip().startswith("| mstats")

    def _assemble(self, uc: UseCase, template: str, ctx: _Context, resolved: ResolvedDataSource,
                  extra: str, *, time_inline: str | None) -> str:
        if self._is_full_search(uc, template):
            return _clean(render(template, ctx))
        base = resolved.base + (f" {time_inline}" if time_inline else "")
        flt = " ".join(p for p in (render(uc.filter, ctx).strip(), extra) if p)
        lines = []
        if resolved.normalization_eval:
            lines.append(base)
            lines.append(f"| {resolved.normalization_eval}")
            if flt:
                lines.append(f"| search {flt}")
        else:
            lines.append(f"{base} {flt}".strip())
        lines.append(render(template, ctx))
        return _clean("\n".join(lines))

    def render_snippet(self, uc: UseCase, template: str, intent: Intent | None = None) -> str:
        """Render an investigation snippet (``| stats ...``) on top of the use-case base search + filter."""
        gen = self.generate(uc, intent, pipeline_override=template)
        return gen.adhoc_spl

    def required_fields(self, ucs: Iterable[UseCase]) -> set[str]:
        out: set[str] = set()
        for uc in ucs:
            out |= uc.required_fields
        return out

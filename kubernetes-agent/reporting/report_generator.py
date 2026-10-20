"""Renders AnalysisResults as text (terminal), Markdown (tickets/wiki) or JSON (automation)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core import __version__
from core.models import AnalysisResult, Finding, Severity

LINE = "=" * 52
SUB = "-" * 52

_COLORS = {
    Severity.CRITICAL: "\033[1;97;41m", Severity.HIGH: "\033[1;31m", Severity.MEDIUM: "\033[33m",
    Severity.LOW: "\033[36m", Severity.INFO: "\033[37m",
}
_RESET, _BOLD, _GREEN = "\033[0m", "\033[1m", "\033[32m"


class ReportGenerator:
    FORMATS = ("text", "markdown", "json")

    def __init__(self, fmt: str = "text", color: bool = False, min_severity: Severity = Severity.INFO,
                 metadata: Optional[Dict[str, Any]] = None, show_facts: bool = True):
        if fmt not in self.FORMATS:
            raise ValueError(f"Unknown format '{fmt}', expected one of {self.FORMATS}")
        self.fmt = fmt
        self.color = color and fmt == "text"
        self.min_severity = min_severity
        self.show_facts = show_facts
        self.metadata = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "agent_version": __version__,
                         "engine": "local rule-based (no external APIs / LLMs)", **(metadata or {})}

    # ---------------------------------------------------------------- public
    def render(self, result: AnalysisResult) -> str:
        return {"text": self._text, "markdown": self._markdown, "json": self._json}[self.fmt](result)

    # ---------------------------------------------------------------- helpers
    def _visible(self, findings: List[Finding]) -> List[Finding]:
        return sorted((f for f in findings if f.severity >= self.min_severity), key=lambda f: f.sort_key())

    def _has_visible(self, result: AnalysisResult) -> bool:
        return bool(self._visible(result.all_findings()))

    def _sev(self, sev: Optional[Severity]) -> str:
        label = sev.label if sev is not None else "Healthy"
        if not self.color:
            return label
        return f"{_COLORS[sev]}{label}{_RESET}" if sev is not None else f"{_GREEN}{label}{_RESET}"

    def _bold(self, s: str) -> str:
        return f"{_BOLD}{s}{_RESET}" if self.color else s

    def _visible_severity(self, result: AnalysisResult) -> Optional[Severity]:
        f = self._visible(result.all_findings())
        return max((x.severity for x in f), default=None)

    # ---------------------------------------------------------------- text
    def _text(self, result: AnalysisResult) -> str:
        out = [LINE, self._bold("KUBERNETES ROOT CAUSE ANALYSIS REPORT"), LINE,
               f"Generated: {self.metadata['generated_at']}   Agent: v{self.metadata['agent_version']}"]
        if self.metadata.get("context"):
            out.append(f"Cluster context: {self.metadata['context']}")
        out.append(f"Analysis engine: {self.metadata['engine']}")
        out.append("")
        out += self._text_block(result)
        if result.children:
            out += ["", LINE, self._bold("RESOURCE SUMMARY"), LINE]
            for child in result.children:
                out += self._summary_lines(child, 0)
            for child in result.children:
                out += self._text_child(child, depth=1)
        out += ["", LINE, "END OF REPORT", LINE]
        return "\n".join(out)

    def _summary_lines(self, res: AnalysisResult, depth: int) -> List[str]:
        sev = self._visible_severity(res)
        primary = self._visible(res.all_findings())
        headline = primary[0].title if primary else "no issues"
        lines = [f"{'  ' * depth}- [{self._sev(sev)}] {res.resource}: {headline}"]
        for child in res.children:
            lines += self._summary_lines(child, depth + 1)
        return lines

    def _text_child(self, res: AnalysisResult, depth: int) -> List[str]:
        if not self._has_visible(res) and not res.collection_errors:
            return []
        out = ["", "#" * 52, f"{'>' * depth} {res.resource}", "#" * 52]
        out += self._text_block(res)
        for child in res.children:
            out += self._text_child(child, depth + 1)
        return out

    def _text_block(self, res: AnalysisResult) -> List[str]:
        findings = self._visible(res.findings)
        out = ["Resource:", f"  {res.resource}", "", "Severity:", f"  {self._sev(self._visible_severity(res))}", ""]
        root_findings = [f for f in findings if not f.is_symptom] or findings
        if root_findings:
            out += ["Primary Root Cause:", f"  {root_findings[0].title}: {root_findings[0].root_cause}", ""]
        if self.show_facts and res.facts:
            out.append("Findings:")
            out += [f"      {fact.strip()}" if fact.startswith("  ") else f"  - {fact}" for fact in res.facts]
            out.append("")
        if findings:
            out.append(self._bold(f"Issues Detected: {len(findings)}"))
            for i, f in enumerate(findings, 1):
                out += self._text_issue(i, f)
        elif not res.children:
            out += ["Issues Detected:", "  None - no diagnostic rule matched; the resource looks healthy."]
        if res.collection_errors:
            out += ["", "Collection Warnings:"] + [f"  ! {e}" for e in res.collection_errors[:10]]
        return out

    def _text_issue(self, idx: int, f: Finding) -> List[str]:
        tag = " (symptom)" if f.is_symptom else ""
        header = f"[{idx}] {f.severity.label.upper()} | {f.title}{tag} | {f.rule_id}"
        if f.container:
            header += f" | container: {f.container}"
        if f.resource.kind not in ("Pod", "Deployment", "Namespace", "Cluster"):
            header += f" | {f.resource}"
        out = [SUB, header, SUB, "Severity:", f"  {self._sev(f.severity)}", "Root Cause:", f"  {f.root_cause}"]
        if f.evidence:
            out.append("Evidence:")
            out += [f"  {e}" for e in f.evidence]
        out += ["Confidence:", f"  {f.confidence}%"]
        if f.related:
            out += ["Related Findings:", f"  {', '.join(dict.fromkeys(f.related))}"]
        if f.recommendations:
            out.append("Recommended Actions:")
            for n, rec in enumerate(f.recommendations, 1):
                lines = rec.splitlines()
                out.append(f"  {n}. {lines[0]}")
                out += [f"       {l}" for l in lines[1:]]
        if f.validation_commands:
            out.append("Validation Commands:")
            out += [f"  {c}" for c in f.validation_commands]
        return out

    # ---------------------------------------------------------------- markdown
    def _markdown(self, result: AnalysisResult) -> str:
        out = ["# Kubernetes Root Cause Analysis Report", "",
               f"*Generated {self.metadata['generated_at']} - agent v{self.metadata['agent_version']} - "
               f"{self.metadata['engine']}*" + (f" - context `{self.metadata['context']}`" if self.metadata.get("context") else ""), ""]
        out += self._md_block(result, 2)
        if result.children:
            out += ["", "## Resource Summary", "", "| Severity | Resource | Top issue |", "|---|---|---|"]
            for child in self._flatten(result.children):
                vis = self._visible(child.all_findings())
                out.append(f"| {self._sev(self._visible_severity(child))} | {child.resource} | "
                           f"{vis[0].title if vis else 'no issues'} |")
            for child in self._flatten(result.children):
                if self._visible(child.findings) or child.collection_errors:
                    out += [""] + self._md_block(child, 3, include_children=False)
        return "\n".join(out) + "\n"

    def _flatten(self, results: List[AnalysisResult]) -> List[AnalysisResult]:
        flat = []
        for r in results:
            flat.append(r)
            flat += self._flatten(r.children)
        return flat

    def _md_block(self, res: AnalysisResult, level: int, include_children: bool = True) -> List[str]:
        h = "#" * level
        findings = self._visible(res.findings)
        out = [f"{h} {res.resource}", "", f"**Severity:** {self._sev(self._visible_severity(res))}", ""]
        if self.show_facts and res.facts:
            out += ["**Findings:**", ""] + [f"- {x}" for x in res.facts] + [""]
        for i, f in enumerate(findings, 1):
            out += [f"{h}# {i}. {f.title}{' (symptom)' if f.is_symptom else ''} - {f.severity.label}", "",
                    f"- **Rule:** `{f.rule_id}`" + (f"  **Container:** `{f.container}`" if f.container else ""),
                    f"- **Confidence:** {f.confidence}%", f"- **Root cause:** {f.root_cause}", "", "**Evidence:**", "", "```"]
            out += f.evidence + ["```", "", "**Recommended actions:**", ""]
            for n, rec in enumerate(f.recommendations, 1):
                if "\n" in rec:
                    first, rest = rec.split("\n", 1)
                    out += [f"{n}. {first}", "", "```yaml", rest, "```"]
                else:
                    out.append(f"{n}. {rec}")
            out += ["", "**Validation commands:**", "", "```bash"] + f.validation_commands + ["```", ""]
        if res.collection_errors:
            out += ["**Collection warnings:**", ""] + [f"- {e}" for e in res.collection_errors[:10]] + [""]
        return out

    # ---------------------------------------------------------------- json
    def _json(self, result: AnalysisResult) -> str:
        sev = result.severity
        payload = {"metadata": self.metadata,
                   "summary": {"severity": sev.label if sev is not None else "Healthy",
                               "issues": len(self._visible(result.all_findings())),
                               "primary_root_cause": result.primary.to_dict() if result.primary else None},
                   "result": result.to_dict()}
        return json.dumps(payload, indent=2, default=str)

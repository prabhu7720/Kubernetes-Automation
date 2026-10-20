"""Base analyzer: runs the rule engine and post-processes findings.

Post-processing pipeline:
  1. de-duplicate identical findings
  2. drop findings below ``min_confidence``
  3. correlate findings sharing a correlation key (primary vs symptom)
  4. redact secrets from evidence/root cause
  5. sort by severity -> root-cause-before-symptom -> confidence
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Sequence, TypeVar

from collectors import CollectorSet
from config.settings import Settings
from core.models import Finding
from core.redact import Redactor
from core.rule_engine import RuleEngine

T = TypeVar("T")
R = TypeVar("R")


class BaseAnalyzer:
    def __init__(self, collectors: CollectorSet, engine: RuleEngine, settings: Settings, redactor: Redactor):
        self.collectors = collectors
        self.engine = engine
        self.settings = settings
        self.redactor = redactor
        self.log = logging.getLogger(self.__class__.__module__)

    def run_rules(self, ctx) -> List[Finding]:
        return self.postprocess(self.engine.evaluate(ctx))

    def postprocess(self, findings: List[Finding]) -> List[Finding]:
        unique: Dict[tuple, Finding] = {}
        for f in findings:
            unique.setdefault(f.fingerprint(), f)
        result = [f for f in unique.values() if f.confidence >= int(self.settings.min_confidence)]
        self.correlate(result)
        for f in result:
            f.evidence = self.redactor.redact_all(f.evidence)
            f.root_cause = self.redactor.redact(f.root_cause, truncate=False)
        return sorted(result, key=lambda f: f.sort_key())

    @staticmethod
    def correlate(findings: List[Finding]) -> None:
        groups: Dict[str, List[Finding]] = {}
        for f in findings:
            if f.correlation_key:
                groups.setdefault(f.correlation_key, []).append(f)
        for group in groups.values():
            if len(group) < 2:
                continue
            group.sort(key=lambda f: f.sort_key())
            primary = group[0]
            for other in group[1:]:
                other.is_symptom = True
                other.related.append(primary.rule_id)
                primary.related.append(other.rule_id)

    def parallel(self, fn: Callable[[T], R], items: Sequence[T]) -> List[R]:
        workers = max(1, int(self.settings.workers))
        if workers == 1 or len(items) <= 1:
            return [fn(i) for i in items]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(fn, items))

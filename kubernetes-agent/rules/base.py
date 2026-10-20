"""Base class for all diagnostic rules.

Contract:
  * ``id``      unique identifier, e.g. "K8S-OOM-001" (required for discovery)
  * ``scopes``  which context types the rule receives (Scope.POD, ...)
  * ``evaluate(ctx)`` returns a list of Findings; it must be side-effect free
    and must not perform I/O (all data comes from the context).
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Iterable, List, Optional, Pattern, Sequence, Tuple, Union

from core.models import Finding, ResourceRef, Scope, Severity


class Rule(ABC):
    id: str = ""
    name: str = ""
    description: str = ""
    category: str = "general"
    scopes: Tuple[Scope, ...] = (Scope.POD,)
    enabled: bool = True

    def __init__(self, settings: Any = None):
        self.settings = settings
        all_overrides = getattr(settings, "rule_overrides", {}) or {}
        self.overrides = dict(all_overrides.get(self.id, {}) or {})

    def applies_to(self, ctx) -> bool:
        return getattr(ctx, "scope", None) in self.scopes

    @abstractmethod
    def evaluate(self, ctx) -> List[Finding]:
        raise NotImplementedError

    # ------------------------------------------------------------ helpers
    def setting(self, name: str, default: Any) -> Any:
        return getattr(self.settings, name, default) if self.settings is not None else default

    @property
    def max_evidence(self) -> int:
        return int(self.setting("max_evidence_lines", 5))

    def patterns(self, key: str, defaults: Iterable[Union[str, Pattern]]) -> List[Pattern]:
        """Default patterns + any extras configured under rule_overrides.<id>.patterns.<key>."""
        extra = (self.overrides.get("patterns") or {}).get(key) or []
        return [p if isinstance(p, re.Pattern) else re.compile(p, re.IGNORECASE)
                for p in list(defaults) + list(extra)]

    def finding(self, ctx, *, title: str, root_cause: str, severity: Severity,
                evidence: Sequence[str] = (), confidence: int = 50,
                recommendations: Sequence[str] = (), commands: Sequence[str] = (),
                container: Optional[str] = None, is_symptom: bool = False,
                correlation_key: Optional[str] = None, resource: Optional[ResourceRef] = None) -> Finding:
        override = self.overrides.get("severity")
        return Finding(
            rule_id=self.id, title=title,
            severity=Severity.parse(override) if override else severity,
            resource=resource or ctx.ref, root_cause=root_cause,
            evidence=[str(e) for e in evidence if e not in (None, "")],
            confidence=confidence,
            recommendations=list(dict.fromkeys(r for r in recommendations if r)),
            validation_commands=list(dict.fromkeys(c for c in commands if c)),
            container=container, is_symptom=is_symptom, category=self.category,
            correlation_key=correlation_key,
        )

    def __repr__(self) -> str:
        return f"<Rule {self.id} {self.name} scopes={[s.value for s in self.scopes]}>"

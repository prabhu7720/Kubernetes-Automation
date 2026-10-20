"""Scores use cases and dashboard blueprints against a parsed intent (deterministic).

score = sum over fully-matched keywords of len(keyword)^1.5 + 0.5 (x1.25 if contiguous)
      + 0.3 per token shared with the use-case name
      + 1.0 domain bonus when a domain keyword is mentioned
Exclusive domains (aws, azure, pci ...) are only eligible when mentioned.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.intent import Intent
from core.models import DashboardBlueprint, UseCase
from core.nlp import normalize

if TYPE_CHECKING:  # pragma: no cover
    from rules.base import RuleRegistry


@dataclass(frozen=True)
class MatchResult:
    use_case: UseCase
    score: float
    matched_keywords: tuple[str, ...]

    @property
    def confidence(self) -> float:
        return round(min(1.0, self.score / 4.5), 2)


@dataclass(frozen=True)
class BlueprintMatch:
    blueprint: DashboardBlueprint
    score: float
    matched_keywords: tuple[str, ...]


def _contiguous(needle: tuple[str, ...], seq: list[str]) -> bool:
    n = len(needle)
    return any(tuple(seq[i:i + n]) == needle for i in range(len(seq) - n + 1))


def _keyword_score(keywords: list[tuple[str, ...]], token_set: set[str], seq: list[str]) -> tuple[float, list[str]]:
    score, matched = 0.0, []
    for kw in keywords:
        if kw and all(t in token_set for t in kw):
            s = len(kw) ** 1.5 + 0.5
            if len(kw) > 1 and _contiguous(kw, seq):
                s *= 1.25
            score += s
            matched.append(" ".join(kw))
    return score, matched


class UseCaseMatcher:
    def __init__(self, registry: "RuleRegistry", min_score: float = 1.5) -> None:
        self.registry = registry
        self.min_score = min_score
        self._uc_index = [
            (uc, [tuple(normalize(k)) for k in uc.keywords], set(normalize(uc.name)))
            for uc in registry.use_cases.values()
        ]
        self._bp_index = [
            (bp, [tuple(normalize(k)) for k in bp.keywords], set(normalize(bp.title)))
            for bp in registry.blueprints.values()
        ]

    def _domain_ok(self, domain: str, tokens: set[str]) -> tuple[bool, float]:
        dk = self.registry.domain_keywords.get(domain, set())
        mentioned = bool(dk & tokens)
        if domain in self.registry.exclusive_domains and not mentioned:
            return False, 0.0
        return True, (1.0 if mentioned else 0.0)

    def match(self, intent: Intent, *, domain: str | None = None, limit: int = 5) -> list[MatchResult]:
        tokens = set(intent.tokens)
        results: list[MatchResult] = []
        for uc, keywords, name_tokens in self._uc_index:
            if domain and uc.domain != domain:
                continue
            eligible, bonus = self._domain_ok(uc.domain, tokens)
            if not eligible:
                continue
            kw_score, matched = _keyword_score(keywords, tokens, intent.tokens)
            name_overlap = len(name_tokens & tokens)
            if kw_score == 0 and name_overlap < 2:
                continue
            score = kw_score + 0.3 * name_overlap + bonus
            if score >= self.min_score:
                results.append(MatchResult(uc, round(score, 3), tuple(matched)))
        results.sort(key=lambda r: (-r.score, r.use_case.id))
        return results[:limit]

    def match_blueprints(self, intent: Intent, limit: int = 3) -> list[BlueprintMatch]:
        tokens = set(intent.tokens)
        out: list[BlueprintMatch] = []
        for bp, keywords, title_tokens in self._bp_index:
            eligible, bonus = self._domain_ok(bp.domain, tokens)
            if not eligible:
                continue
            kw_score, matched = _keyword_score(keywords, tokens, intent.tokens)
            if kw_score == 0:
                continue
            score = kw_score + 0.3 * len(title_tokens & tokens) + bonus
            if score >= self.min_score:
                out.append(BlueprintMatch(bp, round(score, 3), tuple(matched)))
        out.sort(key=lambda m: (-m.score, m.blueprint.id))
        return out[:limit]

    def suggestions(self, intent: Intent, n: int = 5) -> list[str]:
        tokens = set(intent.tokens)
        scored = []
        for uc, keywords, name_tokens in self._uc_index:
            overlap = len(name_tokens & tokens) + sum(1 for kw in keywords for t in kw if t in tokens) * 0.2
            if overlap:
                scored.append((overlap, uc.name))
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [name for _, name in scored[:n]]

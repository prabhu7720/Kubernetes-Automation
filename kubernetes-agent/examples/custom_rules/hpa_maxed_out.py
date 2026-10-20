"""Example plugin rule.

Enable by either:
  * copying this file into rules/, or
  * adding 'examples/custom_rules' to extra_rule_dirs in config/settings.yaml.
"""
from __future__ import annotations

from core.k8s_utils import dig
from core.models import Scope, Severity
from rules.base import Rule


class HPAMaxedOutRule(Rule):
    id = "CUSTOM-HPA-001"
    name = "HPA pinned at maxReplicas"
    category = "scaling"
    scopes = (Scope.DEPLOYMENT,)

    def evaluate(self, ctx):
        hpa = ctx.hpa
        if not hpa:
            return []
        current = dig(hpa, "status", "currentReplicas", default=0)
        maximum = dig(hpa, "spec", "maxReplicas", default=0)
        if not maximum or current < maximum:
            return []
        name = dig(hpa, "metadata", "name")
        return [self.finding(
            ctx, title="HPA at maxReplicas", severity=Severity.MEDIUM,
            root_cause=f"HPA '{name}' is pinned at maxReplicas={maximum}; the workload cannot scale further "
                       "and may be saturated.",
            evidence=[f"currentReplicas={current} maxReplicas={maximum}"], confidence=90,
            recommendations=["Raise maxReplicas or optimise per-pod throughput.",
                             "Check that cluster capacity / quota allows more replicas."],
            commands=[f"{ctx.cmd} describe hpa {name} -n {ctx.namespace}"])]

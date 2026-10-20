"""Deployment-level rules: stuck rollouts, replica creation failures, unavailable replicas."""
from __future__ import annotations

import re
from typing import List

from core.k8s_utils import conditions_map, dig, format_event
from core.models import Scope, Severity

from .base import Rule


def _images(obj) -> List[str]:
    return [c.get("image") for c in dig(obj, "spec", "template", "spec", "containers") or []]


def _cmds(ctx) -> List[str]:
    return [f"{ctx.cmd} rollout status deployment/{ctx.name} -n {ctx.namespace} --timeout=10s",
            f"{ctx.cmd} rollout history deployment/{ctx.name} -n {ctx.namespace}",
            f"{ctx.cmd} describe deployment {ctx.name} -n {ctx.namespace}",
            f"{ctx.cmd} get rs,pods -n {ctx.namespace} -l "
            + ",".join(f"{k}={v}" for k, v in (dig(ctx.deployment, "spec", "selector", "matchLabels") or {}).items())]


class RolloutStuckRule(Rule):
    id = "K8S-DEPLOY-001"
    name = "Rollout stuck (ProgressDeadlineExceeded)"
    category = "deployment"
    scopes = (Scope.DEPLOYMENT,)

    def evaluate(self, ctx):
        cond = conditions_map(ctx.deployment).get("Progressing") or {}
        if cond.get("status") != "False" or cond.get("reason") != "ProgressDeadlineExceeded":
            return []
        st = ctx.deployment.get("status") or {}
        current, previous = ctx.current_replicaset(), ctx.previous_replicaset()
        evidence = [f"Progressing=False reason=ProgressDeadlineExceeded: {cond.get('message')}",
                    f"Replicas desired={dig(ctx.deployment, 'spec', 'replicas', default=1)} updated={st.get('updatedReplicas', 0)} "
                    f"ready={st.get('readyReplicas', 0)} available={st.get('availableReplicas', 0)}",
                    f"progressDeadlineSeconds={dig(ctx.deployment, 'spec', 'progressDeadlineSeconds', default=600)}"]
        root = "The new ReplicaSet's pods never became Ready within the progress deadline, so the rollout stalled."
        if current and previous and _images(current) != _images(previous):
            evidence.append(f"Image change: {_images(previous)} -> {_images(current)}")
            root += " The rollout changed the image - the new version is the prime suspect (see pod findings)."
        return [self.finding(
            ctx, title="Rollout stuck", severity=Severity.HIGH, root_cause=root, evidence=evidence, confidence=92,
            recommendations=["Diagnose the new pods (see pod findings below) - they explain why they are not Ready.",
                             f"Roll back if needed: {ctx.cmd} rollout undo deployment/{ctx.name} -n {ctx.namespace}"],
            commands=_cmds(ctx))]


class ReplicaFailureRule(Rule):
    id = "K8S-DEPLOY-002"
    name = "ReplicaSet cannot create pods"
    category = "deployment"
    scopes = (Scope.DEPLOYMENT,)

    CLASSES = [
        (r"exceeded quota|must specify (limits|requests)", None, None),   # handled by K8S-RES-002
        (r"violates PodSecurity", "The pod template violates the namespace Pod Security Standard (PSA).", 95,
         ["Adjust securityContext (runAsNonRoot, drop capabilities, seccompProfile RuntimeDefault, no privileged/hostPath) "
          "or change the namespace pod-security.kubernetes.io/enforce label deliberately."]),
        (r"admission webhook \"?([\w.-]+)\"? denied", "An admission webhook/policy (OPA Gatekeeper, Kyverno...) rejects the pod.", 93,
         ["Read the policy violation in the event and fix the pod template, or request a policy exception."]),
        (r"failed calling webhook|context deadline exceeded.*webhook|no endpoints available for service",
         "A failing admission webhook (unreachable service or bad certificate) blocks pod creation.", 92,
         ["Check the webhook's backing pods/service and caBundle; consider failurePolicy: Ignore for non-critical webhooks."]),
        (r"serviceaccount \"?([\w.-]+)\"? not found|error looking up service account",
         "The ServiceAccount referenced by the pod template does not exist.", 96,
         ["Create the ServiceAccount or fix serviceAccountName in the template."]),
        (r"is forbidden", "Pod creation is forbidden by RBAC/admission (see message).", 80,
         ["Read the full FailedCreate message to find the rejecting component."]),
    ]

    def evaluate(self, ctx):
        failure = conditions_map(ctx.deployment).get("ReplicaFailure") or {}
        events = ctx.events_with_reason("FailedCreate")
        if failure.get("status") != "True" and not events:
            return []
        text = " ".join([failure.get("message") or ""] + [e.get("message") or "" for e in events])
        for pattern, cause, conf, *rest in self.CLASSES:
            if re.search(pattern, text, re.I):
                if cause is None:
                    return []
                recs = rest[0] if rest else []
                break
        else:
            cause, conf, recs = "The ReplicaSet controller cannot create pods (see FailedCreate events).", 70, []
        return [self.finding(
            ctx, title="Pods cannot be created", severity=Severity.HIGH, root_cause=cause,
            evidence=([f"ReplicaFailure: {failure.get('message')}"] if failure else []) +
                     [format_event(e) for e in events[-3:]],
            confidence=conf, recommendations=recs, commands=_cmds(ctx) +
            [f"{ctx.cmd} get events -n {ctx.namespace} --field-selector reason=FailedCreate"])]


class UnavailableReplicasRule(Rule):
    id = "K8S-DEPLOY-003"
    name = "Unavailable replicas"
    category = "deployment"
    scopes = (Scope.DEPLOYMENT,)

    def evaluate(self, ctx):
        spec_replicas = dig(ctx.deployment, "spec", "replicas", default=1)
        st = ctx.deployment.get("status") or {}
        available = st.get("availableReplicas") or 0
        if dig(ctx.deployment, "spec", "paused"):
            return [self.finding(ctx, title="Rollout paused", severity=Severity.INFO,
                                 root_cause="The deployment rollout is paused; template changes are not rolled out.",
                                 evidence=["spec.paused=true"], confidence=100,
                                 recommendations=[f"Resume: {ctx.cmd} rollout resume deployment/{ctx.name} -n {ctx.namespace}"],
                                 commands=_cmds(ctx))]
        if spec_replicas == 0 or available >= spec_replicas:
            return []
        missing = spec_replicas - available
        sev = Severity.CRITICAL if available == 0 else (Severity.HIGH if missing * 2 >= spec_replicas else Severity.MEDIUM)
        return [self.finding(
            ctx, title="Deployment has unavailable replicas", severity=sev, is_symptom=True,
            root_cause=f"{missing} of {spec_replicas} replicas are unavailable"
                       + (" - the service is DOWN." if available == 0 else " - capacity is degraded.")
                       + " The pod-level findings identify why.",
            evidence=[f"desired={spec_replicas} available={available} ready={st.get('readyReplicas', 0)} "
                      f"updated={st.get('updatedReplicas', 0)} unavailable={st.get('unavailableReplicas', missing)}",
                      f"Pods matched: {len(ctx.pods)}"] + (
                [f"HPA {dig(ctx.hpa, 'metadata', 'name')}: min={dig(ctx.hpa, 'spec', 'minReplicas')} "
                 f"max={dig(ctx.hpa, 'spec', 'maxReplicas')} current={dig(ctx.hpa, 'status', 'currentReplicas')}"]
                if ctx.hpa else []),
            confidence=95, recommendations=["Fix the root cause reported for the deployment's pods."],
            commands=_cmds(ctx))]

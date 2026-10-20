"""CreateContainerConfigError, CreateContainerError and missing Secret/ConfigMap references."""
from __future__ import annotations

import re
from typing import List

from core.k8s_utils import format_event
from core.models import Finding, Scope, Severity
from core.refs import configmap_references, secret_references

from ._common import describe_cmd, events_cmd, termination, waiting
from .base import Rule


class CreateContainerConfigErrorRule(Rule):
    id = "K8S-CFG-001"
    name = "CreateContainerConfigError"
    category = "configuration"
    scopes = (Scope.POD,)

    def evaluate(self, ctx) -> List[Finding]:
        findings = []
        for st in ctx.statuses():
            reason, message = waiting(st)
            if reason != "CreateContainerConfigError":
                continue
            cname = st.get("name")
            evidence = [f"Container: {cname}", f"State: Waiting ({reason})", f"Message: {message}"]
            key = None
            conf = 75
            recs: List[str] = []
            m_secret = re.search(r'secret "([^"]+)" not found', message, re.I)
            m_cm = re.search(r'configmap "([^"]+)" not found', message, re.I)
            m_key = re.search(r"couldn't find key (\S+) in (Secret|ConfigMap) ([\w.-]+)/([\w.-]+)", message, re.I)
            if m_secret:
                name = m_secret.group(1)
                root = f"Secret '{name}' referenced by container '{cname}' does not exist in namespace '{ctx.namespace}'."
                key, conf = f"secret:{ctx.namespace}/{name}", 95
                recs = [f"Create the secret or fix the reference: {ctx.cmd} get secret {name} -n {ctx.namespace}"]
            elif m_cm:
                name = m_cm.group(1)
                root = f"ConfigMap '{name}' referenced by container '{cname}' does not exist in namespace '{ctx.namespace}'."
                key, conf = f"configmap:{ctx.namespace}/{name}", 95
                recs = [f"Create the ConfigMap or fix the reference: {ctx.cmd} get configmap {name} -n {ctx.namespace}"]
            elif m_key:
                k, kind, ns, obj = m_key.groups()
                root = f"{kind} '{obj}' exists but has no key '{k}' required by container '{cname}'."
                conf = 95
                recs = [f"Add key '{k}' to {kind} {ns}/{obj} or fix the key name in the pod spec "
                        "(keys are case-sensitive)."]
            elif re.search(r"runAsNonRoot and image will run as root|non-numeric user", message, re.I):
                root = ("securityContext.runAsNonRoot=true but the image runs as root (or uses a non-numeric USER), "
                        "so the kubelet refuses to start it.")
                conf = 95
                recs = ["Set securityContext.runAsUser to a non-zero UID, or build the image with a numeric non-root USER."]
            else:
                root = f"The kubelet cannot build the container configuration: {message}"
            recs.append("After fixing, the kubelet retries automatically; delete the pod to force immediate recreation.")
            findings.append(self.finding(
                ctx, title="CreateContainerConfigError", severity=Severity.HIGH, root_cause=root,
                evidence=evidence, confidence=conf, recommendations=recs, container=cname, correlation_key=key,
                commands=[describe_cmd(ctx), events_cmd(ctx),
                          f"{ctx.cmd} get secrets,configmaps -n {ctx.namespace}"]))
        return findings


class CreateContainerErrorRule(Rule):
    id = "K8S-CFG-002"
    name = "CreateContainerError / RunContainerError"
    category = "configuration"
    scopes = (Scope.POD,)

    CLASSIFIERS = [
        (r"executable file not found|no such file or directory.*(exec|start)|not found in \$PATH",
         "The container command/entrypoint does not exist in the image.", 92,
         "Fix spec.containers[].command/args or the image ENTRYPOINT; verify with: docker run --entrypoint sh <image>."),
        (r"permission denied", "The entrypoint is not executable or blocked by securityContext.", 85,
         "chmod +x the entrypoint in the image and check runAsUser/readOnlyRootFilesystem."),
        (r"not a directory|is a directory|Are you trying to mount a directory onto a file",
         "A volume is mounted over a path of the wrong type (directory onto file or vice versa).", 90,
         "Use subPath for single-file mounts and verify mountPath matches the type inside the image."),
        (r"exec format error", "The image architecture does not match the node architecture.", 95,
         "Build multi-arch images or schedule onto matching nodes (kubernetes.io/arch)."),
        (r"name .* is already in use|already exists", "Container runtime name conflict (stale container on node).", 70,
         "Usually transient; if persistent, restart the container runtime/kubelet on the node."),
        (r"no command specified", "Neither the image nor the pod spec defines a command.", 95,
         "Set command/args in the pod spec or ENTRYPOINT/CMD in the image."),
        (r"read-only file system", "The process writes to a read-only root filesystem.", 85,
         "Mount an emptyDir at the writable path or disable readOnlyRootFilesystem."),
        (r"cannot allocate memory|resource temporarily unavailable", "The node is out of memory/PIDs.", 75,
         "Check node pressure conditions and pod density on the node."),
    ]

    def evaluate(self, ctx) -> List[Finding]:
        findings = []
        for st in ctx.statuses():
            reason, message = waiting(st)
            term, _ = termination(st)
            if reason not in ("CreateContainerError", "RunContainerError") and \
                    term.get("reason") not in ("StartError", "ContainerCannotRun"):
                continue
            cname = st.get("name")
            if not message:
                message = term.get("message") or ""
            reason = reason or term.get("reason")
            evidence = [f"Container: {cname}", f"Reason: {reason}", f"Message: {' '.join(message.split())[:400]}"]
            evidence += [format_event(e) for e in ctx.events_for_container(cname) if e.get("reason") == "Failed"][-2:]
            root, conf, recs = f"The container runtime failed to create/start the container: {message}", 65, []
            for pattern, cause, c, rec in self.CLASSIFIERS:
                if re.search(pattern, message, re.I):
                    root, conf, recs = cause, c, [rec]
                    break
            spec = ctx.spec_of(cname) or {}
            if spec.get("command") or spec.get("args"):
                evidence.append(f"command={spec.get('command')} args={spec.get('args')}")
            findings.append(self.finding(
                ctx, title=reason, severity=Severity.HIGH, root_cause=root, evidence=evidence,
                confidence=conf, recommendations=recs or ["Inspect the runtime error in the pod events."],
                container=cname, commands=[describe_cmd(ctx), events_cmd(ctx)]))
        return findings


class _MissingRefRule(Rule):
    kind = ""            # "secret" | "configmap"
    label = ""
    category = "configuration"
    scopes = (Scope.POD,)

    def refs(self, ctx):
        raise NotImplementedError

    def existing(self, ctx):
        raise NotImplementedError

    def evaluate(self, ctx) -> List[Finding]:
        existing = self.existing(ctx)
        if existing is None:   # unknown (not collected / forbidden)
            return []
        blocked = ctx.phase == "Pending" or any(
            waiting(st)[0] in ("CreateContainerConfigError", "ContainerCreating") for st in ctx.statuses())
        findings = []
        for name, where in self.refs(ctx).items():
            if name in existing:
                continue
            impact = (" The pod cannot start until it exists." if blocked else
                      " Running containers started before it disappeared; the next restart/reschedule will fail.")
            recs = [f"Create the {self.label} in namespace '{ctx.namespace}' or correct the referenced name "
                    f"({self.label}s are namespace-scoped).",
                    "If it is managed by External Secrets / Sealed Secrets / Vault / GitOps, check that controller's sync status.",
                    f"If the {self.label} is genuinely optional, mark the reference optional: true."]
            findings.append(self.finding(
                ctx, title=f"{self.label} missing", severity=Severity.HIGH if blocked else Severity.MEDIUM,
                root_cause=f"{self.label} '{name}' referenced by the pod does not exist in namespace "
                           f"'{ctx.namespace}'.{impact}",
                evidence=[f"{self.label} '{name}' not found in namespace {ctx.namespace}"] +
                         [f"Referenced by: {w}" for w in where[:6]],
                confidence=98, recommendations=recs, correlation_key=f"{self.kind}:{ctx.namespace}/{name}",
                commands=[f"{ctx.cmd} get {self.kind} {name} -n {ctx.namespace}",
                          f"{ctx.cmd} get {self.kind}s -n {ctx.namespace}",
                          f"{ctx.cmd} get externalsecrets -n {ctx.namespace}   # if External Secrets Operator is used",
                          events_cmd(ctx)]))
        return findings


class MissingSecretRule(_MissingRefRule):
    id = "K8S-CFG-003"
    name = "Referenced Secret missing"
    kind = "secret"
    label = "Secret"

    def refs(self, ctx):
        return secret_references(ctx.pod)

    def existing(self, ctx):
        return ctx.secret_names


class MissingConfigMapRule(_MissingRefRule):
    id = "K8S-CFG-004"
    name = "Referenced ConfigMap missing"
    kind = "configmap"
    label = "ConfigMap"

    def refs(self, ctx):
        return configmap_references(ctx.pod)

    def existing(self, ctx):
        return ctx.configmap_names

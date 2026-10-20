"""Namespace-level rules: terminating namespaces and pending PVCs not tied to a pod analysis."""
from __future__ import annotations

from core.k8s_utils import dig, format_event
from core.models import ResourceRef, Scope, Severity

from .base import Rule


class NamespaceTerminatingRule(Rule):
    id = "K8S-NS-001"
    name = "Namespace stuck terminating"
    category = "namespace"
    scopes = (Scope.NAMESPACE,)

    def evaluate(self, ctx):
        if dig(ctx.namespace_obj, "status", "phase") != "Terminating":
            return []
        conds = dig(ctx.namespace_obj, "status", "conditions") or []
        evidence = [f"{c.get('type')}: {c.get('message')}" for c in conds if c.get("status") == "True"]
        return [self.finding(
            ctx, title="Namespace stuck Terminating", severity=Severity.HIGH,
            root_cause="The namespace is being deleted but remaining resources/finalizers block completion "
                       "(often an unavailable APIService or a controller that no longer runs).",
            evidence=evidence or ["status.phase=Terminating"], confidence=85,
            recommendations=["Find remaining objects and their finalizers (see conditions).",
                             "Check unavailable APIServices: kubectl get apiservice | grep False."],
            commands=[f"{ctx.cmd} get namespace {ctx.name} -o yaml", f"{ctx.cmd} get apiservice"])]


class NamespacePendingPVCRule(Rule):
    id = "K8S-NS-002"
    name = "Pending PVCs in namespace"
    category = "storage"
    scopes = (Scope.NAMESPACE,)

    def evaluate(self, ctx):
        findings = []
        for pvc in ctx.pvcs:
            if dig(pvc, "status", "phase") != "Pending":
                continue
            name = dig(pvc, "metadata", "name")
            sc_name = dig(pvc, "spec", "storageClassName")
            sc = ctx.storage_classes.get(sc_name) if sc_name else next(
                (s for s in ctx.storage_classes.values()
                 if dig(s, "metadata", "annotations", "storageclass.kubernetes.io/is-default-class") == "true"), None)
            if sc and dig(sc, "volumeBindingMode") == "WaitForFirstConsumer":
                continue  # normal until a pod uses it
            events = [e for e in ctx.events if dig(e, "involvedObject", "kind") == "PersistentVolumeClaim"
                      and dig(e, "involvedObject", "name") == name]
            root = (f"PVC '{name}' is Pending: StorageClass '{sc_name or '<default>'}' does not exist."
                    if sc is None else f"PVC '{name}' is Pending: provisioning/binding has not succeeded.")
            findings.append(self.finding(
                ctx, resource=ResourceRef("PersistentVolumeClaim", name, ctx.name), title="PVC Pending",
                severity=Severity.MEDIUM, root_cause=root,
                evidence=[f"storageClass={sc_name or '<default>'}"] + [format_event(e) for e in events[-3:]],
                confidence=85 if sc is None else 70, correlation_key=f"pvc:{ctx.name}/{name}",
                recommendations=["Check provisioner events/logs and the StorageClass configuration."],
                commands=[f"{ctx.cmd} describe pvc {name} -n {ctx.name}", f"{ctx.cmd} get storageclass"]))
        return findings

"""FailedMount / attach errors and PVC / PV health."""
from __future__ import annotations

import re
from typing import List

from core.k8s_utils import dig, format_event
from core.models import Finding, Scope, Severity

from ._common import describe_cmd, events_cmd
from .base import Rule

MOUNT_CLASSIFIERS = [
    (r"Multi-Attach error", "A ReadWriteOnce volume is still attached to another node (typical during a RollingUpdate "
     "of a Deployment using an RWO PVC, or after an unclean node shutdown).", 92,
     ["Use strategy type Recreate (or a StatefulSet) for Deployments with RWO PVCs.",
      "If the old node is gone, check/delete the stale VolumeAttachment: kubectl get volumeattachment."], None),
    (r'secret "([^"]+)" not found', "A Secret used as a volume does not exist.", 95,
     ["Create the Secret or fix the volume's secretName."], "secret"),
    (r'configmap "([^"]+)" not found', "A ConfigMap used as a volume does not exist.", 95,
     ["Create the ConfigMap or fix the volume's configMap.name."], "configmap"),
    (r"driver name ([\w.-]+) not found in the list of registered CSI drivers",
     "The CSI driver is not installed/running on the node.", 92,
     ["Check the CSI node DaemonSet pods on that node (kubectl get pods -A -o wide | grep csi)."], None),
    (r"mount\.nfs|exit status 32|access denied by server",
     "NFS mount failed: server unreachable, export path wrong, or export permissions deny this node.", 85,
     ["Test from the node: showmount -e <server>; check firewall (2049/tcp) and export ACLs."], None),
    (r"permission denied", "The volume mounted but permissions are denied (fsGroup / SELinux / NFS root_squash).", 75,
     ["Set securityContext.fsGroup and fsGroupChangePolicy, or fix ownership on the backing storage."], None),
    (r"exceeded max volume count|maximum number of attachable|AttachVolumeLimitExceeded",
     "The node reached its attachable volume limit.", 90,
     ["Spread volume-heavy pods or use larger instance types."], None),
    (r"VolumeInUse|already attached|is already exclusively attached",
     "The cloud disk is still attached to another instance.", 85,
     ["Detach the disk from the old instance or wait for the attach/detach controller (6 min force-detach)."], None),
    (r"timed out waiting for the condition|Unable to attach or mount volumes",
     "Volume attach/mount timed out; usually a storage backend/CSI or attach problem (see message).", 65,
     ["Describe the PVC/PV and check CSI controller logs."], None),
]


class FailedMountRule(Rule):
    id = "K8S-STOR-001"
    name = "FailedMount / FailedAttachVolume"
    category = "storage"
    scopes = (Scope.POD,)

    def evaluate(self, ctx) -> List[Finding]:
        events = ctx.events_with_reason("FailedMount", "FailedAttachVolume", "FailedMapVolume")
        if not events:
            return []
        # one finding per distinct cause
        groups = {}
        for ev in events:
            msg = ev.get("message") or ""
            match = None
            for pattern, cause, conf, recs, kind in MOUNT_CLASSIFIERS:
                m = re.search(pattern, msg, re.I)
                if m:
                    match = (pattern, cause, conf, recs, kind, m.group(1) if m.groups() else None)
                    break
            key = match[0] if match else "_generic"
            groups.setdefault(key, (match, []))[1].append(ev)
        findings = []
        blocked = ctx.phase == "Pending" or not ctx.is_ready()
        for key, (match, evs) in groups.items():
            latest = evs[-1]
            if match:
                _, cause, conf, recs, kind, obj = match
                corr = f"{kind}:{ctx.namespace}/{obj}" if kind and obj else None
                if obj and kind:
                    cause = cause.replace("does not exist", f"('{obj}') does not exist")
            else:
                cause, conf, recs, corr = "A volume could not be attached or mounted (see event message).", 60, [
                    "Describe the pod/PVC and check CSI driver logs."], None
            vol = re.search(r'volume "([^"]+)"', latest.get("message") or "")
            evidence = [format_event(e) for e in evs[-3:]]
            if vol:
                evidence.insert(0, f"Volume: {vol.group(1)}")
            findings.append(self.finding(
                ctx, title=f"Volume mount failure ({latest.get('reason')})",
                severity=Severity.HIGH if blocked else Severity.MEDIUM, root_cause=cause, evidence=evidence,
                confidence=conf, recommendations=recs, correlation_key=corr,
                commands=[describe_cmd(ctx), events_cmd(ctx), f"{ctx.cmd} get pvc -n {ctx.namespace}",
                          f"{ctx.cmd} get volumeattachment" + (f" | grep {ctx.node_name}" if ctx.node_name else "")]))
        return findings


class PVCStatusRule(Rule):
    id = "K8S-STOR-002"
    name = "PVC / PV problem"
    category = "storage"
    scopes = (Scope.POD,)

    def evaluate(self, ctx) -> List[Finding]:
        findings = []
        for claim, pvc in ctx.pvcs.items():
            cmds = [f"{ctx.cmd} describe pvc {claim} -n {ctx.namespace}", events_cmd(ctx, claim, "PersistentVolumeClaim"),
                    f"{ctx.cmd} get storageclass"]
            corr = f"pvc:{ctx.namespace}/{claim}"
            if pvc is None:
                findings.append(self.finding(
                    ctx, title="PVC missing", severity=Severity.HIGH,
                    root_cause=f"PersistentVolumeClaim '{claim}' referenced by the pod does not exist.",
                    evidence=[f"PVC {ctx.namespace}/{claim}: NOT FOUND"], confidence=97,
                    recommendations=["Create the PVC (or restore it from GitOps/Helm), or fix claimName in the pod spec.",
                                     "For StatefulSets, PVCs are created from volumeClaimTemplates - check the StatefulSet."],
                    correlation_key=corr, commands=cmds))
                continue
            phase = dig(pvc, "status", "phase") or "Unknown"
            sc_name = dig(pvc, "spec", "storageClassName")
            evidence = [f"PVC {claim}: phase={phase} storageClass={sc_name or '<default>'} "
                        f"request={dig(pvc, 'spec', 'resources', 'requests', 'storage')} "
                        f"accessModes={dig(pvc, 'spec', 'accessModes')}"]
            evidence += [format_event(e) for e in (ctx.pvc_events.get(claim) or [])
                         if e.get("type") == "Warning"][-3:]
            if phase == "Pending":
                sc_key = sc_name or "<default>"
                sc = ctx.storage_classes.get(sc_key)
                prov_events = " ".join(e.get("message") or "" for e in ctx.pvc_events.get(claim) or [])
                if sc_key in ctx.storage_classes and sc is None:
                    root, conf = (f"PVC '{claim}' is Pending because StorageClass '{sc_key}' does not exist "
                                  "(or there is no default StorageClass).", 95)
                    recs = ["Create the StorageClass / mark one as default, or set a valid storageClassName."]
                elif sc and dig(sc, "volumeBindingMode") == "WaitForFirstConsumer" and not ctx.node_name:
                    root, conf = (f"PVC '{claim}' waits for the pod to be scheduled (WaitForFirstConsumer); the real "
                                  "blocker is pod scheduling.", 85)
                    recs = ["Resolve the FailedScheduling finding first."]
                elif re.search(r"ProvisioningFailed|failed to provision|error", prov_events, re.I):
                    root, conf = (f"Dynamic provisioning for PVC '{claim}' fails (see PVC events: quota, IAM permissions "
                                  "of the CSI controller, invalid parameters or zone constraints).", 88)
                    recs = ["Check the CSI controller/provisioner logs and cloud quota / IAM permissions."]
                elif not sc_name and not dig(pvc, "spec", "volumeName"):
                    root, conf = (f"PVC '{claim}' is Pending: no matching static PV and no provisioner.", 75)
                    recs = ["Create a matching PV or configure dynamic provisioning."]
                else:
                    root, conf = (f"PVC '{claim}' is Pending: it is not bound to any PersistentVolume.", 70)
                    recs = ["Describe the PVC for provisioning events and check the provisioner."]
                findings.append(self.finding(ctx, title="PVC Pending", severity=Severity.HIGH, root_cause=root,
                                             evidence=evidence, confidence=conf, recommendations=recs,
                                             correlation_key=corr, commands=cmds))
            elif phase == "Lost":
                findings.append(self.finding(
                    ctx, title="PVC Lost", severity=Severity.CRITICAL,
                    root_cause=f"PVC '{claim}' is Lost: its bound PersistentVolume no longer exists.",
                    evidence=evidence, confidence=95, correlation_key=corr, commands=cmds,
                    recommendations=["Restore the PV/backing disk from backup or snapshot and re-bind it.",
                                     "Check reclaimPolicy - use Retain for important data."]))
            pv_name = dig(pvc, "spec", "volumeName")
            pv = ctx.pvs.get(pv_name) if pv_name else None
            if pv_name and pv_name in ctx.pvs and pv is None:
                findings.append(self.finding(
                    ctx, title="PersistentVolume missing", severity=Severity.CRITICAL,
                    root_cause=f"PVC '{claim}' is bound to PV '{pv_name}' which does not exist.",
                    evidence=evidence, confidence=92, correlation_key=corr, commands=cmds,
                    recommendations=["Recreate the PV pointing at the original backing volume, or restore from backup."]))
            elif pv and dig(pv, "status", "phase") in ("Failed", "Released"):
                findings.append(self.finding(
                    ctx, title=f"PersistentVolume {dig(pv, 'status', 'phase')}", severity=Severity.HIGH,
                    root_cause=f"PV '{pv_name}' is in phase {dig(pv, 'status', 'phase')}: "
                               f"{dig(pv, 'status', 'message') or 'reclaim failed or claim was released'}.",
                    evidence=evidence + [f"PV {pv_name}: reclaimPolicy={dig(pv, 'spec', 'persistentVolumeReclaimPolicy')}"],
                    confidence=85, correlation_key=corr, commands=cmds + [f"{ctx.cmd} describe pv {pv_name}"],
                    recommendations=["Inspect the PV and its backing storage; clear spec.claimRef to make a Released PV "
                                     "Available again if the data should be reused."]))
            if "FileSystemResizePending" in {c.get("type") for c in dig(pvc, "status", "conditions") or []}:
                findings.append(self.finding(
                    ctx, title="PVC resize pending", severity=Severity.LOW,
                    root_cause=f"PVC '{claim}' expansion is waiting for a pod restart to resize the filesystem.",
                    evidence=evidence, confidence=90, commands=cmds,
                    recommendations=["Restart the pod to complete the filesystem resize."]))
        return findings

# shellcheck shell=bash
# FailedMount / attach errors and PVC / PV health.

RULE_META[rule_pod_failed_mount]="K8S-STOR-001|storage|FailedMount / FailedAttachVolume"
rule_pod_failed_mount() {
  local evs; evs=$(events_fmt 'FailedMount|FailedAttachVolume|FailedMapVolume')
  [[ -z $evs ]] && return 0
  local root conf=60 corr="" recs=()
  if grep -q 'Multi-Attach error' <<<"$evs"; then
    root="A ReadWriteOnce volume is still attached to another node (RollingUpdate of a Deployment with an RWO PVC, or unclean node shutdown)."; conf=92
    recs=("Use strategy Recreate (or a StatefulSet) for Deployments with RWO PVCs." "Check/delete stale VolumeAttachments: kubectl get volumeattachment.")
  elif [[ $evs =~ secret\ \"([^\"]+)\"\ not\ found ]]; then
    root="Secret '${BASH_REMATCH[1]}' used as a volume does not exist."; conf=95 corr="secret:$CTX_NS/${BASH_REMATCH[1]}"
    recs=("Create the Secret or fix the volume's secretName.")
  elif [[ $evs =~ configmap\ \"([^\"]+)\"\ not\ found ]]; then
    root="ConfigMap '${BASH_REMATCH[1]}' used as a volume does not exist."; conf=95 corr="configmap:$CTX_NS/${BASH_REMATCH[1]}"
    recs=("Create the ConfigMap or fix the volume's configMap.name.")
  elif [[ $evs =~ driver\ name\ ([A-Za-z0-9.-]+)\ not\ found ]]; then
    root="CSI driver ${BASH_REMATCH[1]} is not installed/running on the node."; conf=92
    recs=("Check the CSI node DaemonSet pod on that node.")
  elif grep -qiE 'mount\.nfs|exit status 32|access denied by server' <<<"$evs"; then
    root="NFS mount failed: server unreachable, wrong export path, or export ACL denies this node."; conf=85
    recs=("From the node: showmount -e <server>; check firewall (2049/tcp) and export ACLs.")
  elif grep -qiE 'exceeded max volume count|maximum number of attachable|AttachVolumeLimitExceeded' <<<"$evs"; then
    root="The node reached its attachable volume limit."; conf=90; recs=("Spread volume-heavy pods or use larger instances.")
  elif grep -qiE 'VolumeInUse|already attached|exclusively attached' <<<"$evs"; then
    root="The cloud disk is still attached to another instance."; conf=85; recs=("Detach from the old instance or wait for force-detach.")
  elif grep -qi 'permission denied' <<<"$evs"; then
    root="The volume mounted but permissions are denied (fsGroup / SELinux / NFS root_squash)."; conf=75
    recs=("Set securityContext.fsGroup / fsGroupChangePolicy or fix ownership on the backing storage.")
  else
    root="A volume could not be attached or mounted (see event message)."; recs=("Describe the pod/PVC and check CSI driver logs.")
  fi
  local sev=MEDIUM; { [[ $(pod_phase) == Pending ]] || ! pod_ready; } && sev=HIGH
  emit --sev "$sev" --title "Volume mount failure" --root "$root" --conf "$conf" --corr "$corr" \
    --evidence "$(tail -3 <<<"$evs")" --recs "$(lines "${recs[@]}")" \
    --cmds "$(lines "$(c_describe)" "$(c_events)" "$CMD_PREFIX get pvc -n $CTX_NS" "$CMD_PREFIX get volumeattachment")"
}

RULE_META[rule_pod_pvc]="K8S-STOR-002|storage|PVC / PV problem"
rule_pod_pvc() {
  local f claim
  shopt -s nullglob
  for f in "$CTX"/pvc_*.missing; do
    claim=${f##*/pvc_}; claim=${claim%.missing}
    emit --sev HIGH --title "PVC missing" --conf 97 --corr "pvc:$CTX_NS/$claim" \
      --root "PersistentVolumeClaim '$claim' referenced by the pod does not exist." \
      --evidence "PVC $CTX_NS/$claim: NOT FOUND" \
      --recs "$(lines "Create the PVC (or restore it via GitOps/Helm), or fix claimName." "For StatefulSets, PVCs come from volumeClaimTemplates.")" \
      --cmds "$CMD_PREFIX get pvc -n $CTX_NS"
  done
  for f in "$CTX"/pvc_*.json; do
    claim=${f##*/pvc_}; claim=${claim%.json}
    local phase sc pv ev cmds
    phase=$(jq -r '.status.phase // "Unknown"' "$f"); sc=$(jq -r '.spec.storageClassName // ""' "$f"); pv=$(jq -r '.spec.volumeName // ""' "$f")
    ev=("PVC $claim: phase=$phase storageClass=$(orv "$sc" '<default>') request=$(jq -r '.spec.resources.requests.storage' "$f") accessModes=$(jq -rc '.spec.accessModes' "$f")")
    [[ -f $CTX/pvcevents_$claim.json ]] && while IFS= read -r l; do [[ -n $l ]] && ev+=("$l"); done < <(events_fmt '.*' '.' '' "$CTX/pvcevents_$claim.json" | grep Warning | tail -3)
    cmds=$(lines "$CMD_PREFIX describe pvc $claim -n $CTX_NS" "$(c_events "$claim" PersistentVolumeClaim)" "$CMD_PREFIX get storageclass")
    if [[ $phase == Pending ]]; then
      local root conf rec prov=""
      [[ -f $CTX/pvcevents_$claim.json ]] && prov=$(jq -r '[.items[].message] | join(" ")' "$CTX/pvcevents_$claim.json")
      if [[ -n $sc && -f $CTX/sc_$sc.missing ]]; then
        root="PVC '$claim' is Pending because StorageClass '$sc' does not exist."; conf=95
        rec="Create the StorageClass or set a valid storageClassName."
      elif [[ -n $sc && -f $CTX/sc_$sc.json && $(jq -r '.volumeBindingMode' "$CTX/sc_$sc.json") == WaitForFirstConsumer && -z $(pj '.spec.nodeName // ""') ]]; then
        root="PVC '$claim' waits for the pod to be scheduled (WaitForFirstConsumer); the real blocker is pod scheduling."; conf=85
        rec="Resolve the FailedScheduling finding first."
      elif grep -qiE 'ProvisioningFailed|failed to provision|error' <<<"$prov"; then
        root="Dynamic provisioning for PVC '$claim' fails (quota, CSI controller IAM permissions, invalid parameters, zone constraints)."; conf=88
        rec="Check the CSI provisioner logs and cloud quota / IAM."
      else
        root="PVC '$claim' is Pending: it is not bound to any PersistentVolume."; conf=70
        rec="Describe the PVC for provisioning events."
      fi
      emit --sev HIGH --title "PVC Pending" --root "$root" --conf "$conf" --corr "pvc:$CTX_NS/$claim" \
        --evidence "$(lines "${ev[@]}")" --recs "$rec" --cmds "$cmds"
    elif [[ $phase == Lost ]]; then
      emit --sev CRITICAL --title "PVC Lost" --conf 95 --corr "pvc:$CTX_NS/$claim" \
        --root "PVC '$claim' is Lost: its bound PersistentVolume no longer exists." --evidence "$(lines "${ev[@]}")" \
        --recs "$(lines "Restore the PV/backing disk from backup or snapshot and re-bind it." "Use reclaimPolicy Retain for important data.")" --cmds "$cmds"
    fi
    if [[ -n $pv && -f $CTX/pv_$pv.missing ]]; then
      emit --sev CRITICAL --title "PersistentVolume missing" --conf 92 --corr "pvc:$CTX_NS/$claim" \
        --root "PVC '$claim' is bound to PV '$pv' which does not exist." --evidence "$(lines "${ev[@]}")" \
        --recs "Recreate the PV pointing at the original volume, or restore from backup." --cmds "$cmds"
    elif [[ -n $pv && -f $CTX/pv_$pv.json ]]; then
      local pvphase; pvphase=$(jq -r '.status.phase' "$CTX/pv_$pv.json")
      if [[ $pvphase == Failed || $pvphase == Released ]]; then
        emit --sev HIGH --title "PersistentVolume $pvphase" --conf 85 --corr "pvc:$CTX_NS/$claim" \
          --root "PV '$pv' is $pvphase: $(jq -r '.status.message // "reclaim failed or claim released"' "$CTX/pv_$pv.json")." \
          --evidence "$(lines "${ev[@]}")" --recs "Inspect the PV; clear spec.claimRef to make a Released PV Available again." \
          --cmds "$(lines "$cmds" "$CMD_PREFIX describe pv $pv")"
      fi
    fi
  done
  shopt -u nullglob
}

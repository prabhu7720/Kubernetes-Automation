# shellcheck shell=bash
# Namespace + cluster scope rules.

RULE_META[rule_namespace_terminating]="K8S-NS-001|namespace|Namespace stuck terminating"
rule_namespace_terminating() {
  [[ $(jq -r '.status.phase // ""' "$CTX/namespace.json") == Terminating ]] || return 0
  emit --sev HIGH --title "Namespace stuck Terminating" --conf 85 \
    --root "The namespace is being deleted but remaining resources/finalizers block completion (often an unavailable APIService or a removed controller)." \
    --evidence "$(jq -r '.status.conditions[]? | select(.status == "True") | "\(.type): \(.message)"' "$CTX/namespace.json")" \
    --recs "$(lines "Find remaining objects and their finalizers (see conditions)." "Check unavailable APIServices: kubectl get apiservice | grep False.")" \
    --cmds "$(lines "$CMD_PREFIX get namespace $CTX_NAME -o yaml" "$CMD_PREFIX get apiservice")"
}

RULE_META[rule_namespace_pvc_pending]="K8S-NS-002|storage|Pending PVCs in namespace"
rule_namespace_pvc_pending() {
  local name sc mode
  while IFS=$'\t' read -r name sc mode; do
    [[ $mode == WaitForFirstConsumer ]] && continue
    local root conf=70
    if [[ $mode == MISSING ]]; then root="PVC '$name' is Pending: StorageClass '$sc' does not exist."; conf=85
    else root="PVC '$name' is Pending: provisioning/binding has not succeeded."; fi
    emit --sev MEDIUM --title "PVC Pending" --resource "PersistentVolumeClaim $CTX_NS/$name" --conf "$conf" --corr "pvc:$CTX_NS/$name" \
      --root "$root" --evidence "$(lines "storageClass=$sc" "$(events_fmt '.*' '.' '' <(filter_events "$CTX/events.json" PersistentVolumeClaim "$name") | tail -3)")" \
      --recs "Check provisioner events/logs and the StorageClass configuration." \
      --cmds "$(lines "$CMD_PREFIX describe pvc $name -n $CTX_NS" "$CMD_PREFIX get storageclass")"
  done < <(jq -r --slurpfile sc "$CTX/storageclasses.json" '
      ($sc[0].items // []) as $s
      | ([$s[] | select(.metadata.annotations["storageclass.kubernetes.io/is-default-class"] == "true")][0].metadata.name // "") as $dflt
      | .items[] | select(.status.phase == "Pending") | (.spec.storageClassName // $dflt) as $n
      | [.metadata.name, (if $n == "" then "<default>" else $n end),
         ([$s[] | select(.metadata.name == $n)][0].volumeBindingMode // "MISSING")] | @tsv' "$CTX/persistentvolumeclaims.json")
}

RULE_META[rule_cluster_system_components]="K8S-CLUS-001|cluster|Unhealthy kube-system components"
rule_cluster_system_components() {
  local comp total bad names
  while IFS=$'\t' read -r comp total bad names; do
    [[ $bad -gt 0 ]] || continue
    local sev=MEDIUM impact=""
    if [[ $comp == kube-dns || $comp == coredns ]]; then
      impact=" Cluster DNS is degraded: workloads will see name resolution failures."
      sev=HIGH; [[ $bad -eq $total ]] && sev=CRITICAL
    elif [[ $bad -eq $total ]]; then sev=HIGH; fi
    local first=${names%%,*}
    emit --sev "$sev" --title "kube-system component unhealthy: $comp" --resource "Component kube-system/$comp" --conf 90 \
      --root "$bad/$total '$comp' pods in kube-system are unhealthy.$impact" --evidence "Unhealthy pods: $names" \
      --recs "$(lines "Analyze the failing pod: ./k8s-rca.sh analyze pod $first -n kube-system" "For DaemonSets, check whether failures are limited to specific nodes.")" \
      --cmds "$(lines "$CMD_PREFIX get pods -n kube-system -o wide | grep $comp" "$CMD_PREFIX describe pod $first -n kube-system")"
  done < <(jq -r --argjson thr "$RESTART_THRESHOLD" "$JQ_HEALTH"'
      [.items[] | select(.metadata.namespace == "kube-system")
       | {c: (.metadata.labels["k8s-app"] // .metadata.labels["app.kubernetes.io/name"] // .metadata.labels.component // .metadata.labels.app // .metadata.name),
          n: .metadata.name, bad: (health($thr) > 0)}]
      | group_by(.c)[] | [.[0].c, length, (map(select(.bad)) | length), (map(select(.bad) | .n) | join(","))] | map(tostring) | @tsv' "$CTX/pods.json")
}

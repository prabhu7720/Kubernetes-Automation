# shellcheck shell=bash
# Node health (pod + node scope): NotReady, pressure conditions; pod eviction.

_node_notready() { # scope
  [[ -f $CTX/node.json ]] || return 0
  local status; status=$(node_cond Ready status)
  [[ $status == True || $status == - ]] && return 0
  local n reason msg hb root conf
  n=$(node_name); reason=$(node_cond Ready reason); msg=$(node_cond Ready message); hb=$(node_cond Ready lastHeartbeatTime)
  if [[ $status == Unknown ]] || grep -qi 'stopped posting node status' <<<"$msg"; then
    root="The kubelet stopped reporting to the API server: the node is down/unreachable, the kubelet crashed, or there is a network partition."; conf=88
  elif grep -qiE 'container runtime (is down|not ready)|runtime network not ready' <<<"$msg"; then
    root="The container runtime (containerd/CRI-O) on the node is down or not ready."; conf=90
  elif grep -qi 'PLEG is not healthy' <<<"$msg"; then
    root="PLEG is unhealthy: the kubelet cannot relist containers (runtime overloaded or disk I/O stalls)."; conf=88
  elif grep -qiE 'cni|network plugin' <<<"$msg"; then
    root="The CNI network plugin on the node is not initialized."; conf=90
  elif grep -qiE 'x509|certificate' <<<"$msg"; then
    root="The kubelet's client/serving certificate is invalid or expired."; conf=88
  else
    root="Node $n is NotReady ($reason)."; conf=75
  fi
  local sev=CRITICAL
  [[ $1 == pod ]] && { root="The pod runs on node $n which is NotReady. $root"; sev=HIGH; }
  local taints; taints=$(jq -r '[.spec.taints[]?.key] | join(", ")' "$CTX/node.json")
  emit --sev "$sev" --title "Node NotReady" --resource "Node $n" --root "$root" --conf "$conf" --corr "node-notready:$n" \
    --evidence "$(lines "Node: $n" "Ready=$status reason=$reason" "Message: $msg" "Last heartbeat: $hb" "${taints:+Taints: $taints}" \
                        "$(events_fmt 'NodeNotReady|Rebooted|NodeHasInsufficientMemory|ContainerGCFailed' | tail -3)")" \
    --recs "$(lines "SSH/SSM to the node: systemctl status kubelet containerd; journalctl -u kubelet --since '-30min'." \
                    "Check the cloud instance status checks / hypervisor events." \
                    "If unrecoverable, cordon and drain the node and let the node group replace it." \
                    "Pods on a NotReady node are evicted after tolerationSeconds (default 300s).")" \
    --cmds "$(lines "$CMD_PREFIX describe node $n" "$CMD_PREFIX get node $n -o wide" \
                    "$CMD_PREFIX get pods -A -o wide --field-selector spec.nodeName=$n")"
}

_node_pressure() { # scope
  [[ -f $CTX/node.json ]] || return 0
  local n t; n=$(node_name)
  for t in MemoryPressure DiskPressure PIDPressure NetworkUnavailable; do
    [[ $(node_cond "$t" status) == True ]] || continue
    local expl rec
    case $t in
      MemoryPressure) expl="available memory is below the kubelet eviction threshold"
                      rec="Find the top memory consumers on the node and right-size requests/limits; ensure every pod sets memory requests." ;;
      DiskPressure)   expl="node filesystem / imagefs free space or inodes are below the eviction threshold"
                      rec="Prune images (crictl rmi --prune), check /var/lib/containerd and /var/log; set ephemeral-storage limits and emptyDir sizeLimit." ;;
      PIDPressure)    expl="the node is running out of process IDs"
                      rec="Find pods spawning many processes; set podPidsLimit in the kubelet config." ;;
      NetworkUnavailable) expl="the node network/route is not configured"
                      rec="Check the CNI DaemonSet pod on the node and cloud route tables." ;;
    esac
    local sev=HIGH conf=92 root="Node $n reports $t: $expl. The kubelet taints the node and evicts pods."
    if [[ $1 == pod && $(pj '.status.reason // ""') != Evicted ]]; then
      sev=MEDIUM conf=75 root+=" This pod runs on that node, so it is exposed to evictions and resource starvation."
    fi
    emit --sev "$sev" --title "Node $t" --resource "Node $n" --root "$root" --conf "$conf" --corr "node-$t:$n" \
      --evidence "$(lines "Node $n: $t=True ($(node_cond "$t" reason))" "Message: $(node_cond "$t" message)" "Since: $(node_cond "$t" lastTransitionTime)")" \
      --recs "$rec" --cmds "$(lines "$CMD_PREFIX describe node $n" "$CMD_PREFIX top node $n" "$CMD_PREFIX get pods -A -o wide --field-selector spec.nodeName=$n")"
  done
}

RULE_META[rule_pod_node_notready]="K8S-NODE-001|node|Node NotReady (pod's node)"
rule_pod_node_notready() { _node_notready pod; }
RULE_META[rule_node_notready]="K8S-NODE-001|node|Node NotReady"
rule_node_notready() { _node_notready node; }
RULE_META[rule_pod_node_pressure]="K8S-NODE-002|node|Node pressure (pod's node)"
rule_pod_node_pressure() { _node_pressure pod; }
RULE_META[rule_node_pressure]="K8S-NODE-002|node|Node pressure condition"
rule_node_pressure() { _node_pressure node; }

RULE_META[rule_pod_evicted]="K8S-NODE-003|node|Pod evicted / preempted"
rule_pod_evicted() {
  local reason msg dt
  reason=$(pj '.status.reason // ""'); msg=$(pj '.status.message // ""')
  dt=$(pj '[.status.conditions[]? | select(.type == "DisruptionTarget" and .status == "True")][0].reason // ""')
  [[ $reason == Evicted || -n $dt ]] || return 0
  local root conf recs=()
  if [[ $msg =~ low\ on\ resource:\ ([A-Za-z-]+) ]]; then
    local r=${BASH_REMATCH[1]}
    root="The kubelet evicted the pod because node $(pj '.spec.nodeName') ran low on $r; pods using more $r than they request are evicted first."; conf=95
    recs=("Set $r requests close to real usage (and limits) so the pod is not first in line for eviction."
          "Fix the node pressure source and consider a PriorityClass for critical pods.")
    [[ $r == ephemeral-storage ]] && recs=("Set ephemeral-storage requests/limits, cap emptyDir sizeLimit and reduce log volume." "${recs[@]}")
  elif [[ $dt == PreemptionByScheduler ]]; then
    root="The pod was preempted by the scheduler for a higher-priority pod."; conf=92; recs=("Assign an appropriate PriorityClass or add capacity.")
  elif [[ $dt == DeletionByTaintManager ]]; then
    root="The pod was evicted by a NoExecute taint on its node (node NotReady/unreachable)."; conf=90; recs=("Investigate the node condition.")
  else
    root="The pod was evicted: $msg"; conf=80; recs=("Review node conditions and the eviction message.")
  fi
  recs+=("Clean up evicted pods: $CMD_PREFIX delete pod -n $CTX_NS --field-selector=status.phase=Failed")
  emit --sev HIGH --title "Pod evicted" --root "$root" --conf "$conf" \
    --evidence "$(lines "Pod phase: $(pod_phase) reason: ${reason:-$dt}" "Message: $msg" "Node: $(pj '.spec.nodeName // "-"')")" \
    --recs "$(lines "${recs[@]}")" --cmds "$(lines "$(c_describe)" "$CMD_PREFIX get pods -A --field-selector=status.phase=Failed | grep Evicted")"
}

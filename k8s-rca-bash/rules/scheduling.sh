# shellcheck shell=bash
# FailedScheduling: parses the scheduler's per-predicate breakdown.

# _sched_cause ITEM -> prints "explanation|recommendation" or nothing
_sched_cause() {
  local t=$1
  if [[ $t =~ Insufficient\ ([A-Za-z0-9./-]+) ]]; then
    echo "not enough allocatable ${BASH_REMATCH[1]} for the pod's requests|Lower the pod's requests to realistic values, or add capacity (scale the node group / cluster autoscaler)."
  elif [[ $t =~ untolerated\ taint\ \{?([^}]*)\}? ]]; then
    echo "node taint not tolerated by the pod (${BASH_REMATCH[1]})|Add a matching toleration or target the intended node pool; if the taint is not-ready/unreachable/*-pressure, fix the node instead."
  elif grep -qiE "didn't match Pod's node affinity/selector|didn't match node selector" <<<"$t"; then
    echo "nodeSelector / nodeAffinity matches no available node|Compare the pod nodeSelector/affinity with node labels (kubectl get nodes --show-labels)."
  elif grep -qiE "didn't match pod (anti-)?affinity rules|anti-affinity" <<<"$t"; then
    echo "pod affinity / anti-affinity constraints cannot be satisfied|Relax required anti-affinity to preferred, or add nodes/zones."
  elif grep -qi "topology spread constraints" <<<"$t"; then
    echo "topologySpreadConstraints cannot be satisfied|Use whenUnsatisfiable: ScheduleAnyway or increase maxSkew / zones."
  elif grep -qi "volume node affinity conflict" <<<"$t"; then
    echo "the PersistentVolume is pinned to a zone/node where the pod cannot run|Use volumeBindingMode: WaitForFirstConsumer and ensure nodes exist in the PV's zone."
  elif grep -qiE "unbound immediate PersistentVolumeClaims|persistentvolumeclaim .* not found" <<<"$t"; then
    echo "the pod's PVC is not bound (or missing)|Fix the PVC first (see PVC findings)."
  elif grep -qi "were unschedulable" <<<"$t"; then
    echo "nodes are cordoned (unschedulable)|Uncordon nodes after maintenance: kubectl uncordon <node>."
  elif grep -qi "Too many pods" <<<"$t"; then
    echo "nodes reached their max-pods limit|Increase max pods per node or add nodes."
  elif grep -qi "didn't have free ports" <<<"$t"; then
    echo "requested hostPort already in use on the nodes|Avoid hostPort or run one pod per node."
  elif grep -qi "exceed max volume count" <<<"$t"; then
    echo "nodes reached their maximum attachable volumes|Use larger instance types or spread volume-heavy pods."
  fi
}

RULE_META[rule_pod_scheduling]="K8S-SCHED-001|scheduling|FailedScheduling"
rule_pod_scheduling() {
  local cond_status cond_msg node evs
  cond_status=$(pj '[.status.conditions[]? | select(.type == "PodScheduled")][0].status // "-"')
  cond_msg=$(pj '[.status.conditions[]? | select(.type == "PodScheduled")][0].message // ""')
  node=$(pj '.spec.nodeName // ""')
  evs=$(events_fmt FailedScheduling)
  [[ $cond_status == False || ( -n $evs && $(pod_phase) == Pending && -z $node ) ]] || return 0
  local msg; msg=$(last_event_msg FailedScheduling); [[ -z $msg ]] && msg=$cond_msg
  local body=${msg%% preemption:*}
  body=${body%.}
  [[ $body =~ ^[0-9]+/[0-9]+\ nodes\ are\ available:\ (.*)$ ]] && body=${BASH_REMATCH[1]}
  local causes=() recs=() item count text out
  while IFS= read -r item; do
    [[ -z $item ]] && continue
    if [[ $item =~ ^([0-9]+)\ (.*)$ ]]; then count=${BASH_REMATCH[1]}; text=${BASH_REMATCH[2]}; else count=""; text=$item; fi
    out=$(_sched_cause "$text")
    [[ -z $out ]] && continue
    causes+=("${count:+$count node(s) - }${out%%|*}")
    recs+=("${out#*|}")
  done < <(sed -E 's/, ([0-9]+ )/\n\1/g' <<<"$body")
  local req; req=$(pj '[.spec.containers[] | "\(.resources.requests.cpu // "0") cpu / \(.resources.requests.memory // "0") memory"] | join(" + ")')
  local ev=("Pod phase: $(pod_phase)" "PodScheduled: $cond_status" "Scheduler message: $msg" "Pod requests: $req")
  [[ $(pj '.spec.nodeSelector // {} | length') -gt 0 ]] && ev+=("nodeSelector: $(pj '.spec.nodeSelector | tostring')")
  local as; as=$(events_fmt 'NotTriggerScaleUp|TriggeredScaleUp|FailedScaleUp' | tail -2)
  if [[ -n $as ]]; then
    while IFS= read -r l; do ev+=("$l"); done <<<"$as"
    grep -q NotTriggerScaleUp <<<"$as" && recs+=("Cluster autoscaler will not add a node: no node group can satisfy the pod (max size reached or constraints match no group).")
  fi
  local root conf=70
  if [[ ${#causes[@]} -gt 0 ]]; then
    root="The scheduler cannot place the pod: $(printf '%s; ' "${causes[@]}" | sed 's/; $//')."; conf=92
  else
    root="The scheduler cannot place the pod on any node (see scheduler message)."
    recs=("Review the scheduler message in the pod events.")
  fi
  emit --sev HIGH --title "FailedScheduling" --root "$root" --conf "$conf" \
    --evidence "$(lines "${ev[@]}")" --recs "$(printf '%s\n' "${recs[@]}" | awk '!s[$0]++')" \
    --cmds "$(lines "$(c_describe)" "$(c_events)" \
      "$CMD_PREFIX get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints,CPU:.status.allocatable.cpu,MEM:.status.allocatable.memory" \
      "$CMD_PREFIX describe nodes | grep -A8 'Allocated resources'" "$CMD_PREFIX get pvc -n $CTX_NS")"
}

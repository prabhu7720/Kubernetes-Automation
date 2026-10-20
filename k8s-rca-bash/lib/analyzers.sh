# shellcheck shell=bash
# -----------------------------------------------------------------------------
# analyzers.sh - orchestration for each mode: collect -> facts -> rules.
# Results are written as JSONL (resources/facts/findings/errors) under $WORK
# and rendered by lib/report.jq.
# -----------------------------------------------------------------------------

declare -gA PREFETCH_EVENTS=()

safe_name() { printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '_'; }

# ---------------------------------------------------------------- pod
analyze_pod() { # ns name parent [pod.json]
  local ns=$1 name=$2 parent=$3 src=$4
  local dir="$WORK/ctx/pod_$(safe_name "$ns")_$(safe_name "$name")"
  CUR_RES="Pod $ns/$name"
  add_resource Pod "$name" "$ns" "$parent"
  collect_pod "$ns" "$name" "$dir" "$src"
  CTX=$dir CTX_NS=$ns CTX_NAME=$name
  pod_facts
  run_rules pod
}

pod_facts() {
  local f
  while IFS= read -r f; do add_fact "$f"; done < <(jq -r '
    "Phase: \(.status.phase // "Unknown") (\([.status.containerStatuses[]? | select(.ready)] | length)/\(.spec.containers | length) containers ready)\(if .status.reason then ", reason: " + .status.reason else "" end)",
    "Restart count: \([(.status.initContainerStatuses // [])[], (.status.containerStatuses // [])[] | .restartCount // 0] | add // 0)",
    "QoS class: \(.status.qosClass // "unknown")",
    (((.status.initContainerStatuses // []) | map(. + {k: "init container"})) + ((.status.containerStatuses // []) | map(. + {k: "container"})) | .[]
      | "\(.k) \(.name): \((.state // {}) | keys[0] // "unknown")\(if .state.waiting.reason then " (" + .state.waiting.reason + ")" else "" end), restarts=\(.restartCount // 0)\(if .lastState.terminated then ", last termination: \(.lastState.terminated.reason) (exit \(.lastState.terminated.exitCode)) at \(.lastState.terminated.finishedAt)" else "" end)"),
    (.spec.containers[] | "  \(.name) image: \(.image)",
       "  \(.name) resources: requests cpu=\(.resources.requests.cpu // "unset") memory=\(.resources.requests.memory // "unset") | limits cpu=\(.resources.limits.cpu // "unset") memory=\(.resources.limits.memory // "unset")")
  ' "$CTX/pod.json")
  add_fact "Owner: $(cat "$CTX/owner.txt")"
  if [[ -f $CTX/deployment.json ]]; then
    add_fact "$(jq -r '"Deployment replicas: desired=\(.spec.replicas // 1) available=\(.status.availableReplicas // 0) updated=\(.status.updatedReplicas // 0)"' "$CTX/deployment.json")"
  fi
  if [[ -f $CTX/node.json ]]; then
    add_fact "$(jq -r '([.status.conditions[]? | select(.type=="Ready")][0].status) as $r
      | [.status.conditions[]? | select(.type != "Ready" and .status == "True") | .type] as $p
      | "Node: \(.metadata.name) (\(if $r == "True" then "Ready" else "NotReady" end); \(if ($p|length) > 0 then "pressure: " + ($p|join(", ")) else "no pressure conditions" end))"' "$CTX/node.json")"
  else
    add_fact "Node: $(pj '.spec.nodeName // "not scheduled"')"
  fi
  local p
  for p in "$CTX"/pvc_*.missing; do [[ -e $p ]] && { p=${p##*/pvc_}; add_fact "PVC ${p%.missing}: MISSING"; }; done
  for p in "$CTX"/pvc_*.json; do
    [[ -e $p ]] && add_fact "$(jq -r '"PVC \(.metadata.name): \(.status.phase) (pv=\(.spec.volumeName // "none"), \(.status.capacity.storage // .spec.resources.requests.storage), sc=\(.spec.storageClassName // "<default>"))"' "$p")"
  done
  add_fact "Service account: $(cat "$CTX/sa.name") ($( [[ -f $CTX/sa.json ]] && echo exists || { [[ -f $CTX/sa.missing ]] && echo MISSING || echo 'not verified'; }))"
  if [[ -f $CTX/top.txt ]]; then
    while read -r _ c cpu mem; do add_fact "  $c usage: cpu=$cpu memory=$mem"; done <"$CTX/top.txt"
  fi
  add_fact "$(jq -r '"Events: \(.items | length) total, \([.items[] | select(.type == "Warning")] | length) warnings"' "$CTX/events.json")"
  local cur prev
  cur=$(cd "$CTX/logs" && ls -- *.current 2>/dev/null | sed 's/\.current$//' | paste -sd, -)
  prev=$(cd "$CTX/logs" && ls -- *.previous 2>/dev/null | sed 's/\.previous$//' | paste -sd, -)
  add_fact "Logs collected: current=[${cur}] previous=[${prev}]"
}

# triage: print pod names from a pod-list file, most unhealthy first
unhealthy_pods() { # file max -> "ns<TAB>name" lines
  jq -r --argjson thr "$RESTART_THRESHOLD" "$JQ_HEALTH"'
    [(.items // [])[] | {ns: .metadata.namespace, n: .metadata.name, s: health($thr)} | select(.s > 0)]
    | sort_by(-.s) | .[] | "\(.ns)\t\(.n)"' "$1" | head -n "$2"
}
pod_json_from() { # listfile ns name out
  jq --arg ns "$2" --arg n "$3" '[.items[] | select(.metadata.namespace == $ns and .metadata.name == $n)][0]' "$1" >"$4"
}

# ---------------------------------------------------------------- deployment
deployment_facts() {
  local f
  while IFS= read -r f; do add_fact "$f"; done < <(jq -r --slurpfile pods "$CTX/pods.json" '
    "Replicas: desired=\(.spec.replicas // 1) updated=\(.status.updatedReplicas // 0) ready=\(.status.readyReplicas // 0) available=\(.status.availableReplicas // 0)",
    "Strategy: \(.spec.strategy.type // "RollingUpdate")",
    "Revision: \(.metadata.annotations["deployment.kubernetes.io/revision"] // "?")",
    "Images: \([.spec.template.spec.containers[].image] | join(", "))",
    (.status.conditions[]? | "Condition \(.type)=\(.status) (\(.reason // ""))"),
    "Pods: \($pods[0].items | length) (\($pods[0].items | group_by(.status.phase) | map("\(.[0].status.phase)=\(length)") | join(", ")))"' "$CTX/deploy.json")
}

analyze_deployment() { # ns name parent [prebuilt-ctx-dir] [drill:true|false]
  local ns=$1 name=$2 parent=$3 pre=$4 drill=${5:-true}
  local dir=${pre:-"$WORK/ctx/deploy_$(safe_name "$ns")_$(safe_name "$name")"}
  CUR_RES="Deployment $ns/$name"
  add_resource Deployment "$name" "$ns" "$parent"
  [[ -z $pre ]] && collect_deployment "$ns" "$name" "$dir"
  CTX=$dir CTX_NS=$ns CTX_NAME=$name
  deployment_facts
  run_rules deployment
  [[ $drill == true ]] || return 0
  local key="Deployment $ns/$name" pns pn n=0 tmp
  while IFS=$'\t' read -r pns pn; do
    [[ -z $pn ]] && continue
    tmp="$WORK/ctx/src_$(safe_name "$pn").json"
    pod_json_from "$dir/pods.json" "$pns" "$pn" "$tmp"
    analyze_pod "$pns" "$pn" "$key" "$tmp"
    n=$((n + 1))
  done < <(unhealthy_pods "$dir/pods.json" "$MAX_PODS")
}

# ---------------------------------------------------------------- namespace
analyze_namespace() { # ns
  local ns=$1 dir="$WORK/ctx/ns_$(safe_name "$1")"
  CUR_RES="Namespace $ns"
  add_resource Namespace "$ns" "" ""
  collect_namespace "$ns" "$dir"
  CTX=$dir CTX_NS=$ns CTX_NAME=$ns
  run_rules namespace
  local total unhealthy
  total=$(jq '.items | length' "$dir/pods.json")
  add_fact "Pods: $total ($(jq -r '.items | group_by(.status.phase) | map("\(.[0].status.phase)=\(length)") | join(", ")' "$dir/pods.json"))"
  add_fact "Deployments: $(jq '.items | length' "$dir/deployments.json"), unavailable: $(jq -r '[.items[] | select((.status.availableReplicas // 0) < (.spec.replicas // 1)) | "\(.metadata.name) (\(.status.availableReplicas // 0)/\(.spec.replicas // 1))"] | if length == 0 then "none" else join(", ") end' "$dir/deployments.json")"
  add_fact "PVCs: $(jq -r '(.items | length | tostring) + " (" + (.items | group_by(.status.phase) | map("\(.[0].status.phase)=\(length)") | join(", ")) + ")"' "$dir/persistentvolumeclaims.json")"
  add_fact "Warning events: $(jq '[.items[] | select(.type == "Warning")] | length' "$dir/events.json")"

  # map unhealthy pods -> owning deployment (via ReplicaSet owner refs)
  local map="$dir/pod_owner.tsv"
  jq -r --slurpfile rs "$dir/replicasets.json" '
     ($rs[0].items | map({key: .metadata.name, value: ([.metadata.ownerReferences[]? | select(.kind == "Deployment")][0].name // "")}) | from_entries) as $m
     | .items[] | "\(.metadata.name)\t\(([.metadata.ownerReferences[]? | select(.kind == "ReplicaSet")][0].name // "") as $r | $m[$r] // "")"' \
     "$dir/pods.json" >"$map"
  local list="$dir/unhealthy.tsv"; unhealthy_pods "$dir/pods.json" "$MAX_PODS" >"$list"
  unhealthy=$(grep -c . "$list")
  add_fact "Unhealthy pods: $unhealthy (analyzed up to $MAX_PODS)"
  local root="Namespace $ns"

  # deployments that are unavailable or own unhealthy pods
  local dep
  while read -r dep; do
    [[ -z $dep ]] && continue
    local dd="$WORK/ctx/deploy_$(safe_name "$ns")_$(safe_name "$dep")"; mkdir -p "$dd"
    jq --arg n "$dep" '[.items[] | select(.metadata.name == $n)][0]' "$dir/deployments.json" >"$dd/deploy.json"
    cp "$dir/resourcequotas.json" "$dd/quotas.json"
    build_deployment_ctx "$dd" "$dir/replicasets.json" "$dir/pods.json" "$dir/events.json"
    analyze_deployment "$ns" "$dep" "$root" "$dd" false
  done < <( { jq -r '.items[] | select((.status.availableReplicas // 0) < (.spec.replicas // 1)) | .metadata.name' "$dir/deployments.json"
              cut -f2 "$list" | while read -r p; do awk -F'\t' -v p="$p" '$1 == p && $2 != "" {print $2}' "$map"; done; } | sort -u )

  local pns pn owner tmp
  while IFS=$'\t' read -r pns pn; do
    [[ -z $pn ]] && continue
    owner=$(awk -F'\t' -v p="$pn" '$1 == p {print $2}' "$map")
    tmp="$WORK/ctx/src_$(safe_name "$pn").json"
    pod_json_from "$dir/pods.json" "$pns" "$pn" "$tmp"
    local parent=$root
    [[ -n $owner ]] && parent="Deployment $ns/$owner"
    analyze_pod "$pns" "$pn" "$parent" "$tmp"
  done <"$list"
  CUR_RES=$root
}

# ---------------------------------------------------------------- node
analyze_node() { # name parent [node.json] [events.json]
  local n=$1 parent=$2 dir="$WORK/ctx/node_$(safe_name "$1")"
  CUR_RES="Node $n"
  add_resource Node "$n" "" "$parent"
  collect_node "$n" "$dir" "$3" "$4"
  CTX=$dir CTX_NS="" CTX_NAME=$n
  add_fact "$(jq -r '([.status.conditions[]? | select(.type == "Ready")][0].status) as $r
     | "Ready: \($r); pressure: \([.status.conditions[]? | select(.type != "Ready" and .status == "True") | .type] | if length == 0 then "none" else join(", ") end)"' "$dir/node.json")"
  add_fact "$(jq -r '.status.nodeInfo | "Kubelet: \(.kubeletVersion)  runtime: \(.containerRuntimeVersion)  OS: \(.osImage)  arch: \(.architecture)"' "$dir/node.json")"
  run_rules node
}

analyze_node_full() { # name : node + its unhealthy pods
  analyze_node "$1" ""
  local pods="$WORK/ctx/node_$(safe_name "$1")/pods.json"
  kube_json "$pods" get pods --all-namespaces --field-selector "spec.nodeName=$1" || true
  local pns pn tmp
  while IFS=$'\t' read -r pns pn; do
    [[ -z $pn ]] && continue
    tmp="$WORK/ctx/src_$(safe_name "$pn").json"; pod_json_from "$pods" "$pns" "$pn" "$tmp"
    analyze_pod "$pns" "$pn" "Node $1" "$tmp"
  done < <(unhealthy_pods "$pods" "$MAX_PODS")
}

# ---------------------------------------------------------------- cluster
analyze_cluster() {
  local dir="$WORK/ctx/cluster" ctxname
  ctxname=$(kube config current-context 2>/dev/null || echo current-context)
  [[ -n $KCONTEXT ]] && ctxname=$KCONTEXT
  CUR_RES="Cluster $ctxname"
  add_resource Cluster "$ctxname" "" ""
  collect_cluster "$dir"
  CTX=$dir CTX_NS="" CTX_NAME=$ctxname
  run_rules cluster
  local root="Cluster $ctxname"
  add_fact "Server version: $(cat "$dir/version.txt")"
  add_fact "$(jq -r '[.items[] | ([.status.conditions[]? | select(.type == "Ready")][0].status == "True")] | "Nodes: \(length) (Ready=\(map(select(.)) | length), NotReady=\(map(select(. | not)) | length))"' "$dir/nodes.json")"
  add_fact "Pods: $(jq -r '(.items | length | tostring) + " (" + (.items | group_by(.status.phase) | map("\(.[0].status.phase)=\(length)") | join(", ")) + ")"' "$dir/pods.json")"
  add_fact "Deployments with unavailable replicas: $(jq -r '[.items[] | select((.status.availableReplicas // 0) < (.spec.replicas // 1)) | "\(.metadata.namespace)/\(.metadata.name)"] | if length == 0 then "none" else join(", ") end' "$dir/deployments.json")"
  add_fact "cert-manager: $([[ -f $dir/certificates.json ]] && jq -r '"\(.items | length) certificates"' "$dir/certificates.json" || echo 'not installed')"

  local nname
  while read -r nname; do
    [[ -z $nname ]] && continue
    jq --arg n "$nname" '[.items[] | select(.metadata.name == $n)][0]' "$dir/nodes.json" >"$dir/n_$nname.json"
    analyze_node "$nname" "$root" "$dir/n_$nname.json" "$dir/nodeevents.json"
  done < <(jq -r '.items[].metadata.name' "$dir/nodes.json")

  local list="$dir/unhealthy.tsv" pns pn tmp
  unhealthy_pods "$dir/pods.json" "$MAX_PODS" >"$list"
  for pns in $(cut -f1 "$list" | sort -u); do PREFETCH_EVENTS[$pns]=1; done
  CUR_RES=$root; add_fact "Unhealthy pods analyzed: $(grep -c . "$list")"
  while IFS=$'\t' read -r pns pn; do
    [[ -z $pn ]] && continue
    tmp="$WORK/ctx/src_$(safe_name "$pns")_$(safe_name "$pn").json"; pod_json_from "$dir/pods.json" "$pns" "$pn" "$tmp"
    analyze_pod "$pns" "$pn" "$root" "$tmp"
  done <"$list"
}

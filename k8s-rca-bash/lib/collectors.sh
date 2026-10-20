# shellcheck shell=bash
# -----------------------------------------------------------------------------
# collectors.sh - read-only data collection into per-resource context dirs.
#
# Pod context dir layout ($CTX):
#   pod.json events.json logs/<c>.current logs/<c>.previous rs.json deployment.json
#   owner.txt node.json pvc_<claim>.json|.missing pv_<name>.json sc_<name>.json|.missing
#   pvcevents_<claim>.json sa.json|sa.missing secrets.txt configmaps.txt top.txt
# -----------------------------------------------------------------------------

# Namespace events are fetched once per run and filtered locally.
ns_events_file() { # ns -> path
  local f="$WORK/cache/events_$1.json"
  [[ -f $f ]] || kube_json "$f" get events -n "$1" || true
  echo "$f"
}

filter_events() { # srcfile kind name > out
  jq --arg k "$2" --arg n "$3" '{items: [(.items // [])[] | select(.involvedObject.kind == $k and .involvedObject.name == $n)]}' "$1"
}

collect_pod() { # ns name dir [pod.json source]
  local ns=$1 name=$2 d=$3 src=$4
  mkdir -p "$d/logs"
  if [[ -n $src ]]; then
    cp "$src" "$d/pod.json"
  else
    kube_json "$d/pod.json" get pod "$name" -n "$ns"
    case $? in 1) die "Pod $ns/$name not found" ;; 2) die "cannot read pod $ns/$name (see warnings / RBAC)" ;; esac
  fi
  local CTX=$d

  # ---- events
  if [[ -n ${PREFETCH_EVENTS[$ns]:-} ]]; then
    filter_events "$(ns_events_file "$ns")" Pod "$name" >"$d/events.json"
  else
    kube_json "$d/events.json" get events -n "$ns" --field-selector "involvedObject.kind=Pod,involvedObject.name=$name" || true
  fi

  # ---- logs (current + previous only where they exist)
  if [[ $COLLECT_LOGS == true ]]; then
    local cname rc state last
    while IFS=$'\t' read -r cname rc state last; do
      if [[ $state == running || $state == terminated || $rc -gt 0 || $last == true ]]; then
        kube logs "$name" -n "$ns" -c "$cname" --tail="$LOG_TAIL" >"$d/logs/$cname.current" 2>/dev/null || rm -f "$d/logs/$cname.current"
      fi
      if [[ $rc -gt 0 || $last == true ]]; then
        kube logs "$name" -n "$ns" -c "$cname" --tail="$LOG_TAIL" --previous >"$d/logs/$cname.previous" 2>/dev/null || rm -f "$d/logs/$cname.previous"
      fi
    done < <(jq -r '((.status.initContainerStatuses // []) + (.status.containerStatuses // []))[]
                    | [.name, (.restartCount // 0), ((.state // {}) | keys[0] // "none"), (.lastState.terminated != null)] | map(tostring) | @tsv' "$d/pod.json")
  fi

  # ---- owner chain: Pod -> ReplicaSet -> Deployment (or STS/DS/Job)
  local okind oname
  read -r okind oname < <(jq -r '[.metadata.ownerReferences[]? | select(.controller)][0] | "\(.kind // "-") \(.name // "-")"' "$d/pod.json")
  echo "$okind/$oname" >"$d/owner.txt"
  if [[ $okind == ReplicaSet ]]; then
    if kube_json "$d/rs.json" get replicaset "$oname" -n "$ns"; then
      read -r okind oname < <(jq -r '[.metadata.ownerReferences[]? | select(.controller)][0] | "\(.kind // "-") \(.name // "-")"' "$d/rs.json")
      if [[ $okind == Deployment ]]; then
        kube_json "$d/deployment.json" get deployment "$oname" -n "$ns" || rm -f "$d/deployment.json"
        echo "Deployment/$oname <- $(cat "$d/owner.txt")" >"$d/owner.txt"
      fi
    fi
  fi

  # ---- node
  local node; node=$(jq -r '.spec.nodeName // empty' "$d/pod.json")
  if [[ -n $node ]]; then
    local nf; nf=$(kube_cached "node_$node" get node "$node") && cp "$nf" "$d/node.json"
  fi

  # ---- PVC / PV / StorageClass
  local claim
  while read -r claim; do
    [[ -z $claim ]] && continue
    kube_json "$d/pvc_$claim.json" get pvc "$claim" -n "$ns"
    case $? in
      1) touch "$d/pvc_$claim.missing"; rm -f "$d/pvc_$claim.json"; continue ;;
      2) rm -f "$d/pvc_$claim.json"; continue ;;
    esac
    if [[ -n ${PREFETCH_EVENTS[$ns]:-} ]]; then
      filter_events "$(ns_events_file "$ns")" PersistentVolumeClaim "$claim" >"$d/pvcevents_$claim.json"
    else
      kube_json "$d/pvcevents_$claim.json" get events -n "$ns" \
        --field-selector "involvedObject.kind=PersistentVolumeClaim,involvedObject.name=$claim" || true
    fi
    local pv sc
    pv=$(jq -r '.spec.volumeName // empty' "$d/pvc_$claim.json")
    [[ -n $pv ]] && { kube_json "$d/pv_$pv.json" get pv "$pv" || { [[ $? == 1 ]] && touch "$d/pv_$pv.missing"; }; }
    sc=$(jq -r '.spec.storageClassName // empty' "$d/pvc_$claim.json")
    if [[ -n $sc ]]; then
      local scf; scf=$(kube_cached "sc_$sc" get storageclass "$sc"); [[ $? == 1 ]] && touch "$d/sc_$sc.missing" || cp "$scf" "$d/sc_$sc.json"
    fi
  done < <(jq -r '.metadata.name as $p | .spec.volumes[]? | (.persistentVolumeClaim.claimName // (if .ephemeral then "\($p)-\(.name)" else empty end))' "$d/pod.json")

  # ---- service account
  local sa; sa=$(jq -r '.spec.serviceAccountName // .spec.serviceAccount // "default"' "$d/pod.json")
  echo "$sa" >"$d/sa.name"
  kube_json "$d/sa.json" get serviceaccount "$sa" -n "$ns"
  case $? in 1) touch "$d/sa.missing"; rm -f "$d/sa.json" ;; 2) rm -f "$d/sa.json" ;; esac

  # ---- secret / configmap names (only when referenced; never values)
  if jq -e '[.. | objects | (.secretKeyRef?, .secretRef?, .secret?, .imagePullSecrets?) | select(. != null)] | length > 0' "$d/pod.json" >/dev/null; then
    [[ -f $WORK/cache/secrets_$ns.txt ]] || kube_names secrets "$ns" "$WORK/cache/secrets_$ns.txt"
    [[ -f $WORK/cache/secrets_$ns.txt ]] && cp "$WORK/cache/secrets_$ns.txt" "$d/secrets.txt"
  fi
  if jq -e '[.. | objects | (.configMapKeyRef?, .configMapRef?, .configMap?) | select(. != null)] | length > 0' "$d/pod.json" >/dev/null; then
    [[ -f $WORK/cache/configmaps_$ns.txt ]] || kube_names configmaps "$ns" "$WORK/cache/configmaps_$ns.txt"
    [[ -f $WORK/cache/configmaps_$ns.txt ]] && cp "$WORK/cache/configmaps_$ns.txt" "$d/configmaps.txt"
  fi

  # ---- metrics (optional, metrics-server)
  if [[ $COLLECT_METRICS == true && $(jq -r '.status.phase' "$d/pod.json") == Running ]]; then
    kube top pod "$name" -n "$ns" --containers --no-headers >"$d/top.txt" 2>/dev/null || rm -f "$d/top.txt"
  fi
  return 0
}

collect_deployment() { # ns name dir
  local ns=$1 name=$2 d=$3
  mkdir -p "$d"
  kube_json "$d/deploy.json" get deployment "$name" -n "$ns"
  case $? in 1) die "Deployment $ns/$name not found" ;; 2) die "cannot read deployment $ns/$name" ;; esac
  PREFETCH_EVENTS[$ns]=1
  local sel; sel=$(jq -r '[.spec.selector.matchLabels // {} | to_entries[] | "\(.key)=\(.value)"] | join(",")' "$d/deploy.json")
  kube_json "$d/rs_all.json" get replicasets -n "$ns" ${sel:+-l "$sel"} || true
  kube_json "$d/pods_all.json" get pods -n "$ns" ${sel:+-l "$sel"} || true
  kube_json "$d/quotas.json" get resourcequotas -n "$ns" || true
  build_deployment_ctx "$d" "$d/rs_all.json" "$d/pods_all.json" "$(ns_events_file "$ns")"
}

# build_deployment_ctx dir rsfile podsfile eventsfile  (dir/deploy.json must exist)
build_deployment_ctx() {
  local d=$1
  jq --slurpfile dep "$d/deploy.json" '{items: [(.items // [])[] | select(any(.metadata.ownerReferences[]?; .uid == $dep[0].metadata.uid))]}' "$2" >"$d/rs.json"
  jq --slurpfile rs "$d/rs.json" '($rs[0].items | map(.metadata.uid)) as $u
      | {items: [(.items // [])[] | select(any(.metadata.ownerReferences[]?; .uid as $x | $u | index($x)))]}' "$3" >"$d/pods.json"
  jq --slurpfile dep "$d/deploy.json" --slurpfile rs "$d/rs.json" '
      ($rs[0].items | map(.metadata.name)) as $rsn | $dep[0].metadata.name as $dn
      | {items: [(.items // [])[] | select((.involvedObject.kind == "Deployment" and .involvedObject.name == $dn)
                                       or (.involvedObject.kind == "ReplicaSet" and (.involvedObject.name as $x | $rsn | index($x))))]}' "$4" >"$d/events.json"
  [[ -f $d/quotas.json ]] || echo '{"items":[]}' >"$d/quotas.json"
}

collect_namespace() { # ns dir
  local ns=$1 d=$2
  mkdir -p "$d"
  kube_json "$d/namespace.json" get namespace "$ns"
  case $? in 1) die "Namespace $ns not found" ;; 2) die "cannot read namespace $ns" ;; esac
  PREFETCH_EVENTS[$ns]=1
  cp "$(ns_events_file "$ns")" "$d/events.json"
  local r
  for r in pods deployments replicasets persistentvolumeclaims resourcequotas; do
    kube_json "$d/$r.json" get "$r" -n "$ns" || true
  done
  kube_json "$d/storageclasses.json" get storageclasses || true
}

collect_cluster() { # dir
  local d=$1
  mkdir -p "$d"
  kube_json "$d/nodes.json" get nodes || true
  kube_json "$d/pods.json" get pods --all-namespaces || true
  kube_json "$d/deployments.json" get deployments --all-namespaces || true
  kube_json "$d/nodeevents.json" get events --all-namespaces --field-selector involvedObject.kind=Node || true
  kube_json "$d/certificates.json" get certificates.cert-manager.io --all-namespaces
  [[ $? == 3 ]] && rm -f "$d/certificates.json"   # cert-manager not installed
  kube version -o json 2>/dev/null | jq -r '.serverVersion.gitVersion // "unknown"' >"$d/version.txt" || echo unknown >"$d/version.txt"
  [[ $COLLECT_METRICS == true ]] && { kube top nodes --no-headers >"$d/topnodes.txt" 2>/dev/null || rm -f "$d/topnodes.txt"; }
  return 0
}

collect_node() { # name dir [node.json] [events.json]
  local n=$1 d=$2
  mkdir -p "$d"
  if [[ -n $3 ]]; then cp "$3" "$d/node.json"; else
    kube_json "$d/node.json" get node "$n"
    case $? in 1) die "Node $n not found" ;; 2) die "cannot read node $n" ;; esac
  fi
  if [[ -n $4 ]]; then filter_events "$4" Node "$n" >"$d/events.json"; else
    kube_json "$d/events.json" get events --all-namespaces --field-selector "involvedObject.kind=Node,involvedObject.name=$n" || true
  fi
}

# shellcheck shell=bash
# CreateContainerConfigError, CreateContainerError, missing Secret / ConfigMap.

RULE_META[rule_pod_create_config_error]="K8S-CFG-001|configuration|CreateContainerConfigError"
rule_pod_create_config_error() {
  local name rc ready wr wm tr tc lr lc fin img init st
  while IFS=$'\t' read -r name rc ready wr wm tr tc lr lc fin img init st; do
    [[ $wr == CreateContainerConfigError ]] || continue
    local root conf=75 corr="" recs=()
    if [[ $wm =~ secret\ \"([^\"]+)\"\ not\ found ]]; then
      root="Secret '${BASH_REMATCH[1]}' referenced by container '$name' does not exist in namespace '$CTX_NS'."
      conf=95 corr="secret:$CTX_NS/${BASH_REMATCH[1]}"
      recs=("Create the secret or fix the reference: $CMD_PREFIX get secret ${BASH_REMATCH[1]} -n $CTX_NS")
    elif [[ $wm =~ configmap\ \"([^\"]+)\"\ not\ found ]]; then
      root="ConfigMap '${BASH_REMATCH[1]}' referenced by container '$name' does not exist in namespace '$CTX_NS'."
      conf=95 corr="configmap:$CTX_NS/${BASH_REMATCH[1]}"
      recs=("Create the ConfigMap or fix the reference: $CMD_PREFIX get configmap ${BASH_REMATCH[1]} -n $CTX_NS")
    elif [[ $wm =~ couldn\'t\ find\ key\ ([^ ]+)\ in\ (Secret|ConfigMap)\ ([^ ]+) ]]; then
      root="${BASH_REMATCH[2]} '${BASH_REMATCH[3]}' exists but has no key '${BASH_REMATCH[1]}' required by container '$name'."
      conf=95 recs=("Add the key or fix the key name in the pod spec (keys are case-sensitive).")
    elif grep -qiE 'runAsNonRoot and image will run as root|non-numeric user' <<<"$wm"; then
      root="securityContext.runAsNonRoot=true but the image runs as root (or uses a non-numeric USER)."
      conf=95 recs=("Set securityContext.runAsUser to a non-zero UID or build the image with a numeric non-root USER.")
    else
      root="The kubelet cannot build the container configuration: $wm"
    fi
    recs+=("After fixing, the kubelet retries automatically; delete the pod to force immediate recreation.")
    emit --sev HIGH --title "CreateContainerConfigError" --root "$root" --conf "$conf" --container "$name" --corr "$corr" \
      --evidence "$(lines "Container: $name" "State: Waiting ($wr)" "Message: $wm")" --recs "$(lines "${recs[@]}")" \
      --cmds "$(lines "$(c_describe)" "$(c_events)" "$CMD_PREFIX get secrets,configmaps -n $CTX_NS")"
  done < <(statuses_tsv)
}

RULE_META[rule_pod_create_container_error]="K8S-CFG-002|configuration|CreateContainerError / RunContainerError"
rule_pod_create_container_error() {
  local name rc ready wr wm tr tc lr lc fin img init st
  while IFS=$'\t' read -r name rc ready wr wm tr tc lr lc fin img init st; do
    local reason=$wr
    if [[ $wr != CreateContainerError && $wr != RunContainerError ]]; then
      [[ $tr == StartError || $tr == ContainerCannotRun || $lr == StartError || $lr == ContainerCannotRun ]] || continue
      reason=$([[ $tr != - ]] && echo "$tr" || echo "$lr")
      wm=$(jq -r --arg c "$name" '[.status.containerStatuses[]? | select(.name == $c)][0] | (.state.terminated.message // .lastState.terminated.message // "")' "$CTX/pod.json")
    fi
    local root="The container runtime failed to create/start the container: $wm" conf=65 rec="Inspect the runtime error in the pod events."
    if grep -qiE 'executable file not found|not found in \$PATH|no such file or directory' <<<"$wm"; then
      root="The container command/entrypoint does not exist in the image."; conf=92
      rec="Fix spec.containers[].command/args or the image ENTRYPOINT."
    elif grep -qiE 'not a directory|is a directory|mount a directory onto a file' <<<"$wm"; then
      root="A volume is mounted over a path of the wrong type (directory onto file or vice versa)."; conf=90
      rec="Use subPath for single-file mounts and verify mountPath."
    elif grep -qi 'exec format error' <<<"$wm"; then
      root="The image architecture does not match the node."; conf=95; rec="Build multi-arch images or schedule onto matching nodes."
    elif grep -qi 'permission denied' <<<"$wm"; then
      root="The entrypoint is not executable or blocked by securityContext."; conf=85; rec="chmod +x the entrypoint; check runAsUser / readOnlyRootFilesystem."
    elif grep -qi 'no command specified' <<<"$wm"; then
      root="Neither the image nor the pod spec defines a command."; conf=95; rec="Set command/args or ENTRYPOINT/CMD."
    elif grep -qi 'read-only file system' <<<"$wm"; then
      root="The process writes to a read-only root filesystem."; conf=85; rec="Mount an emptyDir at the writable path."
    fi
    emit --sev HIGH --title "$reason" --root "$root" --conf "$conf" --container "$name" \
      --evidence "$(lines "Container: $name" "Reason: $reason" "Message: $wm" "$(events_fmt Failed '.' "$name" | tail -2)")" \
      --recs "$rec" --cmds "$(lines "$(c_describe)" "$(c_events)")"
  done < <(statuses_tsv)
}

# refs KIND(secret|configmap) -> "name<TAB>where" (non-optional references only)
_refs() {
  jq -r --arg k "$1" '
    (if $k == "secret" then ["secretKeyRef","secretRef","secret","secretName"] else ["configMapKeyRef","configMapRef","configMap","name"] end) as [$kr,$fr,$vol,$vn]
    | [(.spec.initContainers // [])[], .spec.containers[]] as $cs
    | ( $cs[] | .name as $c
        | ((.env // [])[] | .name as $e | .valueFrom[$kr]? // empty | select(.optional != true) | "\(.name)\tenv \($e) (key \(.key)) in container \($c)"),
          ((.envFrom // [])[] | .[$fr]? // empty | select(.optional != true) | "\(.name)\tenvFrom in container \($c)") ),
      ( (.spec.volumes // [])[] | .name as $v
        | ((.[$vol]? // empty | select(.optional != true) | "\(.[$vn])\tvolume \($v)"),
           ((.projected.sources // [])[] | .[$vol]? // empty | select(.optional != true) | "\(.name)\tprojected volume \($v)")) )' "$CTX/pod.json"
}

_missing_ref() { # kind label namesfile
  local kind=$1 label=$2 file=$3
  [[ -f $file ]] || return 0      # unknown (not collected / RBAC) -> skip
  local blocked=false
  [[ $(pod_phase) == Pending ]] && blocked=true
  local n
  while read -r n; do
    [[ -z $n ]] && continue
    grep -qx -- "$n" "$file" && continue
    local where; where=$(_refs "$kind" | awk -F'\t' -v n="$n" '$1 == n {print "Referenced by: " $2}' | head -6)
    local impact=" Running containers started before it disappeared; the next restart/reschedule will fail." sev=MEDIUM
    [[ $blocked == true ]] && { impact=" The pod cannot start until it exists."; sev=HIGH; }
    emit --sev "$sev" --title "$label missing" --conf 98 --corr "$kind:$CTX_NS/$n" \
      --root "$label '$n' referenced by the pod does not exist in namespace '$CTX_NS'.$impact" \
      --evidence "$(lines "$label '$n' not found in namespace $CTX_NS" "$where")" \
      --recs "$(lines "Create the $label in namespace '$CTX_NS' or correct the referenced name (${label}s are namespace-scoped)." \
                      "If managed by External Secrets / Sealed Secrets / Vault / GitOps, check that controller's sync status." \
                      "If genuinely optional, mark the reference optional: true.")" \
      --cmds "$(lines "$CMD_PREFIX get $kind $n -n $CTX_NS" "$CMD_PREFIX get ${kind}s -n $CTX_NS" \
                      "$CMD_PREFIX get externalsecrets -n $CTX_NS   # if External Secrets Operator is used" "$(c_events)")"
  done < <(_refs "$kind" | cut -f1 | sort -u)
}

RULE_META[rule_pod_missing_secret]="K8S-CFG-003|configuration|Referenced Secret missing"
rule_pod_missing_secret() { _missing_ref secret Secret "$CTX/secrets.txt"; }

RULE_META[rule_pod_missing_configmap]="K8S-CFG-004|configuration|Referenced ConfigMap missing"
rule_pod_missing_configmap() { _missing_ref configmap ConfigMap "$CTX/configmaps.txt"; }

# shellcheck shell=bash
# CrashLoopBackOff, frequent restarts, failed (non-restarting) containers.

# _exit_analysis CONTAINER CODE  -> sets globals XA_ROOT XA_CONF XA_EV (newline list) XA_REC
_exit_analysis() {
  local c=$1 code=$2 hits
  XA_ROOT="Container '$c' repeatedly exits with code $code ($(exit_meaning "$code"))."
  XA_CONF=70
  XA_REC=$(exit_rec "$code")
  hits=$(log_hits "$FATAL_RE" "$c")
  if grep -qi 'exec format error' <<<"$hits"; then
    XA_ROOT="The image was built for a different CPU architecture than the node (exec format error)."; XA_CONF=95
    XA_REC="Build a multi-arch image (docker buildx --platform linux/amd64,linux/arm64) or pin nodeSelector kubernetes.io/arch."
  elif grep -qi 'address already in use' <<<"$hits"; then
    XA_ROOT="The application cannot bind its port because it is already in use (sidecar / hostNetwork conflict)."; XA_CONF=85
    XA_REC="Change the listening port or remove the conflicting sidecar / hostNetwork usage."
  elif grep -qi 'permission denied' <<<"$hits"; then
    XA_ROOT="The process hits a filesystem permission error (runAsUser/fsGroup vs file ownership, read-only root FS)."; XA_CONF=75
    XA_REC="Align securityContext (runAsUser, fsGroup) with file ownership or mount a writable emptyDir."
  elif [[ -n $hits ]]; then
    XA_ROOT+=" The container logs show the application failing - see the log evidence."; XA_CONF=85
  elif [[ $code == 126 || $code == 127 ]]; then
    XA_CONF=85
  fi
  if [[ -n $hits ]]; then
    XA_EV=$hits
  else
    XA_EV=$(last_log_lines "$c" 3)
    [[ -z $XA_EV ]] && XA_EV="No previous log output: the process failed before logging (check command/args, entrypoint, mounted files)."
  fi
}

RULE_META[rule_pod_crashloop]="K8S-CRASH-001|workload|CrashLoopBackOff"
rule_pod_crashloop() {
  local name rc ready wr wm tr tc lr lc fin img init st
  while IFS=$'\t' read -r name rc ready wr wm tr tc lr lc fin img init st; do
    [[ $wr == CrashLoopBackOff ]] || continue
    local code=$lc reason=$lr; [[ $code == - ]] && { code=$tc; reason=$tr; }
    local ev=("Container: $name" "State: Waiting (CrashLoopBackOff)" "Restart count: $rc"
              "Last termination reason: $reason" "Exit Code: $code")
    [[ $wm != - ]] && ev+=("Back-off: $wm")
    local root conf symptom=false recs=()
    if [[ $reason == OOMKilled ]]; then
      root="CrashLoopBackOff of '$name' is a symptom: the container is repeatedly OOMKilled (see the OOMKilled finding)."
      conf=90 symptom=true recs=("Resolve the OOMKilled finding (memory limit / leak).")
    elif [[ $(event_count Killing 'liveness probe' "$name") -gt 0 ]]; then
      root="CrashLoopBackOff of '$name' is driven by liveness probe failures: the kubelet keeps killing the container."
      conf=85 symptom=true recs=("Resolve the liveness probe failure finding.")
    else
      _exit_analysis "$name" "$code"
      root=$XA_ROOT conf=$XA_CONF recs=("$XA_REC")
      while IFS= read -r l; do ev+=("$l"); done <<<"$XA_EV"
      if [[ -n $(log_hits "$DEP_RE" "$name" 1) ]]; then
        symptom=true
        root+=" The process aborts because a startup dependency fails (network/DNS/TLS/RBAC) - the dependency findings carry the actual root cause."
        recs=("Fix the dependency failure reported in the related network/DNS/TLS/RBAC findings." "${recs[@]}")
      else
        recs+=("Check related findings (DNS, connection refused, missing config) - dependency failures at startup commonly cause crash loops.")
      fi
    fi
    [[ $init == true ]] && root="[init container] $root The pod cannot start until this init container succeeds."
    emit --sev HIGH --title "CrashLoopBackOff" --root "$root" --conf "$conf" --container "$name" --symptom "$symptom" \
      --evidence "$(lines "${ev[@]}")" --recs "$(lines "${recs[@]}")" \
      --cmds "$(lines "$(c_logs "$name" prev)" "$(c_logs "$name")" "$(c_describe)" "$CMD_PREFIX get pod $CTX_NAME -n $CTX_NS -o yaml")"
  done < <(statuses_tsv)
}

RULE_META[rule_pod_restarts]="K8S-CRASH-002|workload|Frequent container restarts"
rule_pod_restarts() {
  local name rc ready wr wm tr tc lr lc fin img init st
  while IFS=$'\t' read -r name rc ready wr wm tr tc lr lc fin img init st; do
    [[ $rc -ge $RESTART_THRESHOLD && $wr != CrashLoopBackOff && $lr != OOMKilled ]] || continue
    if [[ $(event_count Killing 'liveness probe' "$name") -gt 0 ]]; then
      emit --sev MEDIUM --title "Frequent container restarts" --container "$name" --conf 85 --symptom true \
        --root "Container '$name' restarts because its liveness probe fails (see the liveness finding)." \
        --evidence "$(lines "Container: $name" "Restart count: $rc" "Liveness kill events: $(event_count Killing 'liveness probe' "$name")")" \
        --recs "Resolve the liveness probe failure finding." --cmds "$(c_describe)"
      continue
    fi
    _exit_analysis "$name" "$lc"
    emit --sev MEDIUM --title "Frequent container restarts" --container "$name" --conf $((XA_CONF > 60 ? XA_CONF - 10 : 50)) \
      --root "Container '$name' restarted $rc times. $XA_ROOT" \
      --evidence "$(lines "Container: $name" "Restart count: $rc" "Last termination: $lr (exit $lc)" "$XA_EV")" \
      --recs "$XA_REC" --cmds "$(lines "$(c_logs "$name" prev)" "$(c_describe)")"
  done < <(statuses_tsv)
}

RULE_META[rule_pod_container_failed]="K8S-CRASH-003|workload|Container terminated with error"
rule_pod_container_failed() {
  [[ $(pj '.status.reason // ""') == Evicted ]] && return 0
  local name rc ready wr wm tr tc lr lc fin img init st
  while IFS=$'\t' read -r name rc ready wr wm tr tc lr lc fin img init st; do
    [[ $tc != - && $tc != 0 && $tr != OOMKilled && $tr != Completed ]] || continue
    _exit_analysis "$name" "$tc"
    local sev=MEDIUM; [[ $(pod_phase) == Failed ]] && sev=HIGH
    emit --sev "$sev" --title "Container terminated with error" --container "$name" --conf "$XA_CONF" \
      --corr "termination:$CTX_NS/$CTX_NAME/$name" --root "$XA_ROOT" \
      --evidence "$(lines "Container: $name" "Pod phase: $(pod_phase)" "restartPolicy: $(pj '.spec.restartPolicy // "Always"')" "Exit Code: $tc" "$XA_EV")" \
      --recs "$XA_REC" --cmds "$(lines "$(c_logs "$name")" "$(c_describe)")"
  done < <(statuses_tsv)
}

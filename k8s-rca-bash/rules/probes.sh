# shellcheck shell=bash
# Readiness / liveness / startup probe failures.

# _probe_check TYPE SPECKEY RULE_TITLE
_probe_check() {
  local type=$1 key=$2 c
  while read -r c; do
    [[ -z $c ]] && continue
    local evs; evs=$(events_fmt Unhealthy "^$type probe (failed|errored)" "$c")
    [[ -z $evs ]] && continue
    local count msg probe port path timeout delay declared ready rc
    count=$(event_count Unhealthy "^$type probe (failed|errored)" "$c")
    msg=$(tail -1 <<<"$evs" | sed -E 's/^Event [^:]+\): //')
    probe=$(cspec "$c" ".$key")
    port=$(cspec "$c" "(.$key.httpGet.port // .$key.tcpSocket.port // .$key.grpc.port)")
    path=$(cspec "$c" ".$key.httpGet.path")
    timeout=$(cspec "$c" ".$key.timeoutSeconds // 1"); delay=$(cspec "$c" ".$key.initialDelaySeconds // 0")
    ready=$(jq -r --arg c "$c" '[.status.containerStatuses[]? | select(.name == $c)][0].ready // false' "$CTX/pod.json")
    rc=$(jq -r --arg c "$c" '[.status.containerStatuses[]? | select(.name == $c)][0].restartCount // 0' "$CTX/pod.json")
    declared=$(jq -r --arg c "$c" --arg p "$port" '[.spec.containers[] | select(.name == $c)][0].ports // [] |
                 if length == 0 then "unknown" elif any(.[]; (.containerPort | tostring) == $p or .name == $p) then "yes" else "no" end' "$CTX/pod.json")

    local root conf recs=()
    if [[ $msg =~ statuscode:\ *([0-9]+) ]]; then
      local code=${BASH_REMATCH[1]}
      case $code in
        404) root="The probe path returns HTTP 404: the configured path is wrong or the health endpoint is not registered."; conf=90
             recs=("Fix httpGet.path to the application's real health endpoint.") ;;
        401|403) root="The health endpoint requires authentication (HTTP $code)."; conf=88
             recs=("Exempt the health endpoint from authentication middleware.") ;;
        5*) root="The application reports itself unhealthy (HTTP $code); typically a failing dependency check (DB, cache, downstream API) or an internal error."; conf=80
             recs=("Check application logs around the failure time for the failing dependency."
                   "Keep liveness checks shallow; put dependency checks in readiness only.") ;;
        *) root="The health endpoint returned unexpected HTTP $code."; conf=70 ;;
      esac
    elif grep -qiE 'server gave HTTP response to HTTPS client|first record does not look like a TLS handshake' <<<"$msg"; then
      root="Probe scheme mismatch: HTTPS probe against an HTTP port (or vice versa)."; conf=92
      recs=("Set httpGet.scheme to match what the application serves.")
    elif grep -qi 'connection refused' <<<"$msg"; then
      root="Nothing is listening on the probe port when the probe runs: the app has not started yet (initialDelaySeconds=$delay may be too short), listens on another port, or binds to 127.0.0.1 instead of 0.0.0.0."; conf=80
      recs=("Confirm the app listens on the probe port on 0.0.0.0 (kubectl exec ... -- ss -tlnp)."
            "For slow-starting apps add a startupProbe instead of a long initialDelaySeconds.")
    elif grep -qiE 'timeout|deadline exceeded|Client\.Timeout|timed out' <<<"$msg"; then
      root="The health endpoint responds slower than timeoutSeconds=${timeout}s (CPU throttling, GC pauses, thread exhaustion, heavy health handler)."; conf=75
      recs=("Increase timeoutSeconds (currently ${timeout}s) and check CPU throttling / limits." "Make the health handler lightweight.")
    elif grep -qiE 'OCI runtime exec failed|executable file not found|no such file' <<<"$msg"; then
      root="The exec probe command does not exist in the container image."; conf=90
      recs=("Fix exec.command or install the tool in the image.")
    else
      root="$type probe is failing; see the probe failure message in the evidence."; conf=60
    fi
    if [[ $declared == no ]]; then
      root="The probe targets port '$port' which the container does not expose. $root"; conf=$((conf > 88 ? conf : 88))
      recs=("Point the probe at the port the application actually listens on." "${recs[@]}")
    fi
    local ev=("Container: $c" "$type probe: $(jq -rc . <<<"$probe")" "Probe failures: $count" "Last failure: $msg"
              "Container ready: $ready  restarts: $rc")
    [[ $declared == no ]] && ev+=("Probe port '$port' is NOT declared in the container ports")
    local sev=HIGH
    case $type in
      Readiness) recs+=("While not ready the pod is removed from Service endpoints; verify with kubectl get endpoints.")
                 if [[ $ready == true ]]; then sev=LOW; elif [[ $(pod_phase) != Running ]]; then sev=MEDIUM; fi ;;
      Liveness)  local kills; kills=$(event_count Killing 'liveness probe' "$c")
                 [[ $kills -gt 0 ]] && ev+=("Kubelet restarted the container after liveness failures $kills time(s)")
                 [[ $rc -gt 0 ]] || sev=MEDIUM
                 recs+=("Liveness failures restart the container - do not depend on external services; use a generous failureThreshold."
                        "Use a startupProbe so liveness only starts after boot.") ;;
      Startup)   recs+=("Raise failureThreshold x periodSeconds if the app legitimately needs longer to boot.") ;;
    esac
    emit --sev "$sev" --title "$type probe failure" --root "$root" --conf "$conf" --container "$c" \
      --evidence "$(lines "${ev[@]}")" --recs "$(lines "${recs[@]}")" \
      --cmds "$(lines "$(c_describe)" "$(c_events)" "$(c_logs "$c")" \
        "$CMD_PREFIX exec -it $CTX_NAME -n $CTX_NS -c $c -- sh -c 'wget -qO- http://127.0.0.1:$(orv "$port" '<port>')$(orv "$path" '/') || curl -sv http://127.0.0.1:$(orv "$port" '<port>')$(orv "$path" '/')'")"
  done < <(jq -r '.spec.containers[].name' "$CTX/pod.json")
}

RULE_META[rule_pod_readiness]="K8S-PROBE-001|probes|Readiness probe failure"
rule_pod_readiness() { _probe_check Readiness readinessProbe; }

RULE_META[rule_pod_liveness]="K8S-PROBE-002|probes|Liveness probe failure"
rule_pod_liveness() { _probe_check Liveness livenessProbe; }

RULE_META[rule_pod_startup]="K8S-PROBE-003|probes|Startup probe failure"
rule_pod_startup() { _probe_check Startup startupProbe; }

# shellcheck shell=bash
# Resource exhaustion: usage near limits, missing requests/limits, quota exhaustion.

RULE_META[rule_pod_resource_exhaustion]="K8S-RES-001|resources|Resource exhaustion"
rule_pod_resource_exhaustion() {
  local c
  # live usage vs limits (metrics-server)
  if [[ -f $CTX/top.txt ]]; then
    local _p cpu mem
    while read -r _p c cpu mem; do
      local ml cl mp cp
      ml=$(cspec "$c" '.resources.limits.memory'); cl=$(cspec "$c" '.resources.limits.cpu')
      mp=$(pct "$(to_bytes "$mem")" "$(to_bytes "$(orv "$ml" '')")")
      cp=$(pct "$(to_milli "$cpu")" "$(to_milli "$(orv "$cl" '')")")
      if [[ -n $mp ]] && awk -v a="$mp" -v b="$MEMORY_USAGE_WARN_PCT" 'BEGIN{exit !(a >= b)}'; then
        emit --sev MEDIUM --title "Memory usage near limit" --container "$c" --conf 88 --corr "memory:$CTX_NS/$CTX_NAME/$c" \
          --root "Container '$c' uses $mp% of its memory limit; it is at imminent risk of OOMKill." \
          --evidence "Memory usage: $mem / limit $ml" --recs "Raise the memory limit or reduce memory footprint; check for leaks." \
          --cmds "$CMD_PREFIX top pod $CTX_NAME -n $CTX_NS --containers"
      fi
      if [[ -n $cp ]] && awk -v a="$cp" -v b="$CPU_USAGE_WARN_PCT" 'BEGIN{exit !(a >= b)}'; then
        emit --sev MEDIUM --title "CPU at limit (throttling)" --container "$c" --conf 72 \
          --root "Container '$c' uses $cp% of its CPU limit; CFS throttling is likely, slowing requests and causing probe timeouts." \
          --evidence "CPU usage: $cpu / limit $cl" --recs "Raise or remove the CPU limit (keep requests); verify with container_cpu_cfs_throttled_periods_total." \
          --cmds "$CMD_PREFIX top pod $CTX_NAME -n $CTX_NS --containers"
      fi
    done <"$CTX/top.txt"
  fi
  # BestEffort containers
  local missing; missing=$(pj '[.spec.containers[] | select((.resources.requests // {} | length) == 0 and (.resources.limits // {} | length) == 0) | .name] | join(", ")')
  if [[ -n $missing ]]; then
    local sev=LOW; { ! pod_ready || [[ $(pod_restarts) -gt 0 ]]; } && sev=MEDIUM
    emit --sev "$sev" --title "No resource requests/limits" --conf 90 \
      --root "Container(s) $missing define no requests or limits (QoS $(pj '.status.qosClass // "BestEffort"')): the scheduler cannot place them correctly and they are evicted / OOM-killed first under node pressure." \
      --evidence "Containers without requests/limits: $missing" \
      --recs "$(lines "Set CPU/memory requests from observed usage and a memory limit." "Enforce defaults with a LimitRange in the namespace.")" \
      --cmds "$CMD_PREFIX get limitrange -n $CTX_NS"
  fi
}

# quota exhaustion: FailedCreate events + ResourceQuota usage (deployment & namespace scope)
_quota() {
  local evs; evs=$(events_fmt FailedCreate 'exceeded quota|must specify (limits|requests)|forbidden: (maximum|minimum)' | tail -3)
  if [[ -n $evs ]]; then
    local root corr=""
    if [[ $evs =~ exceeded\ quota:\ ([A-Za-z0-9.-]+) ]]; then
      root="Pod creation is rejected because ResourceQuota '${BASH_REMATCH[1]}' in namespace '$CTX_NS' is exhausted; new replicas cannot be created."
      corr="quota:$CTX_NS/${BASH_REMATCH[1]}"
    elif grep -q 'must specify' <<<"$evs"; then
      root="Pod creation is rejected: a ResourceQuota requires requests/limits but the pod template does not set them."
    else
      root="Pod creation is rejected by a LimitRange (requests/limits outside the allowed range)."
    fi
    emit --sev HIGH --title "Pod creation blocked by quota/LimitRange" --conf 96 --corr "$corr" --root "$root" --evidence "$evs" \
      --recs "$(lines "Increase the quota, reduce requested resources, or scale down other workloads." "Set requests/limits in the pod template (or a LimitRange default).")" \
      --cmds "$(lines "$CMD_PREFIX describe resourcequota -n $CTX_NS" "$CMD_PREFIX describe limitrange -n $CTX_NS")"
  fi
  local qf=$1; [[ -f $qf ]] || return 0
  local q r hard used
  while IFS=$'\t' read -r q r hard used; do
    local h u p
    if [[ $r == *cpu* ]]; then h=$(to_milli "$hard"); u=$(to_milli "$used"); else h=$(to_bytes "$hard"); u=$(to_bytes "$used"); fi
    p=$(pct "$u" "$h"); [[ -z $p ]] && continue
    awk -v a="$p" -v b="$QUOTA_WARN_PCT" 'BEGIN{exit !(a >= b)}' || continue
    local sev=MEDIUM title="Quota nearly exhausted"
    awk -v a="$p" 'BEGIN{exit !(a >= 100)}' && { sev=HIGH; title="Quota exhausted"; }
    emit --sev "$sev" --title "$title" --resource "ResourceQuota $CTX_NS/$q" --conf 95 --corr "quota:$CTX_NS/$q" \
      --root "ResourceQuota $CTX_NS/$q: $r at $p% ($used/$hard)." --evidence "$r: used=$used hard=$hard" \
      --recs "Raise the quota or reclaim unused resources before the next rollout/scale-up." \
      --cmds "$CMD_PREFIX describe resourcequota $q -n $CTX_NS"
  done < <(jq -r '.items[]? | .metadata.name as $q | (.status.hard // {}) as $h | (.status.used // {}) as $u
                  | $h | keys[] | [$q, ., $h[.], ($u[.] // "0")] | @tsv' "$qf")
}

RULE_META[rule_deployment_quota]="K8S-RES-002|resources|ResourceQuota / LimitRange exhaustion"
rule_deployment_quota() { _quota "$CTX/quotas.json"; }
RULE_META[rule_namespace_quota]="K8S-RES-002|resources|ResourceQuota / LimitRange exhaustion"
rule_namespace_quota() { _quota "$CTX/resourcequotas.json"; }

# shellcheck shell=bash
# OOMKilled detection (container memory limit or node-level OOM).

RULE_META[rule_pod_oom]="K8S-OOM-001|resources|Container OOMKilled"
rule_pod_oom() {
  local name rc ready wr wm tr tc lr lc fin img init st
  while IFS=$'\t' read -r name rc ready wr wm tr tc lr lc fin img init st; do
    local reason code conf when
    if [[ $tr == OOMKilled ]]; then reason=OOMKilled code=$tc conf=95 when=current
    elif [[ $lr == OOMKilled ]]; then reason=OOMKilled code=$lc conf=95 when=last
    elif [[ $tc == 137 ]]; then reason=$(orv "$tr" Error) code=137 conf=65 when=current
    elif [[ $lc == 137 ]]; then reason=$(orv "$lr" Error) code=137 conf=65 when=last
    else continue; fi

    local lim req ev=() recs=() root runtime="" hit
    lim=$(cspec "$name" '.resources.limits.memory'); req=$(cspec "$name" '.resources.requests.memory')
    ev=("Container: $name" "Exit Code: $code" "Termination Reason: $reason ($when state)" "Restart count: $rc"
        "Memory limit: $(orv "$lim" 'NOT SET')" "Memory request: $(orv "$req" 'NOT SET')")
    [[ $fin != - ]] && ev+=("Terminated at: $fin")
    if [[ -f $CTX/top.txt ]]; then
      local mem; mem=$(awk -v c="$name" '$2 == c {print $4}' "$CTX/top.txt")
      if [[ -n $mem ]]; then
        local p; p=$(pct "$(to_bytes "$mem")" "$(to_bytes "$(orv "$lim" '')")")
        ev+=("Current memory usage: $mem${p:+ ($p% of limit)}")
      fi
    fi
    hit=$(log_hits 'java\.lang\.OutOfMemoryError' "$name" 1); [[ -n $hit ]] && runtime=JVM
    [[ -z $hit ]] && { hit=$(log_hits 'JavaScript heap out of memory|Allocation failed' "$name" 1); [[ -n $hit ]] && runtime=Node.js; }
    [[ -z $hit ]] && { hit=$(log_hits 'runtime: out of memory|cannot allocate memory' "$name" 1); [[ -n $hit ]] && runtime=Go; }
    [[ -z $hit ]] && { hit=$(log_hits '\bMemoryError\b' "$name" 1); [[ -n $hit ]] && runtime=Python; }
    [[ -n $hit ]] && ev+=("$hit")

    if [[ $lim != - ]]; then
      root="Container '$name' exceeded its configured memory limit ($lim) and was killed by the kernel OOM killer."
    else
      root="Container '$name' has no memory limit and was OOM killed because the node ran out of memory (node-level OOM)."
    fi
    [[ -n $runtime ]] && root+=" The $runtime runtime also reported running out of heap."
    if [[ -f $CTX/node.json && $(node_cond MemoryPressure status) == True ]]; then
      ev+=("Node $(node_name) currently reports MemoryPressure=True")
    fi

    recs=("Increase the memory limit for container '$name' (currently $(orv "$lim" unset)); size it from observed peak usage plus 20-30% headroom."
          "Check for a memory leak: compare memory growth over time (container_memory_working_set_bytes) and capture a heap profile."
          "Monitor usage after the change (kubectl top / Prometheus); consider VPA recommendations.")
    case $runtime in
      JVM) recs+=("Align JVM heap with the container limit: -XX:MaxRAMPercentage=75 (avoid -Xmx above the limit).") ;;
      Node.js) recs+=("Set --max-old-space-size to ~75% of the container memory limit.") ;;
      Go) recs+=("Set GOMEMLIMIT to ~90% of the container memory limit.") ;;
    esac
    [[ $req != "$lim" ]] && recs+=("For critical workloads set memory request == limit (Guaranteed QoS).")

    emit --sev HIGH --title "Container OOMKilled" --root "$root" --conf "$conf" --container "$name" \
      --corr "termination:$CTX_NS/$CTX_NAME/$name" \
      --evidence "$(lines "${ev[@]}")" --recs "$(lines "${recs[@]}")" \
      --cmds "$(lines "$CMD_PREFIX top pod $CTX_NAME -n $CTX_NS --containers" "$(c_describe)" "$(c_logs "$name" prev)" \
                      "$CMD_PREFIX get pod $CTX_NAME -n $CTX_NS -o jsonpath='{.status.containerStatuses[*].lastState}'")"
  done < <(statuses_tsv)
}

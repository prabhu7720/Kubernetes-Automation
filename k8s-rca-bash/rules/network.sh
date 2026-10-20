# shellcheck shell=bash
# DNS failures, connection refused, network timeouts, CNI / sandbox failures.

RULE_META[rule_pod_dns]="K8S-NET-001|network|DNS resolution failure"
rule_pod_dns() {
  local hits; hits=$(log_hits "$DNS_RE")
  [[ -z $hits ]] && return 0
  local hosts cluster_hosts root conf
  hosts=$(grep -oE "lookup [A-Za-z0-9.-]+|ENOTFOUND [A-Za-z0-9.-]+|EAI_AGAIN [A-Za-z0-9.-]+|UnknownHostException:? [A-Za-z0-9.-]+|resolve host:? '?[A-Za-z0-9.-]+" <<<"$hits" \
          | awk '{print $NF}' | tr -d "'" | awk '!s[$0]++')
  cluster_hosts=$(grep -E '\.svc(\.|$)|\.cluster\.local$|^[A-Za-z0-9-]+$' <<<"$hosts")
  if grep -qiE 'on [0-9.]+:53: .*(i/o timeout|read udp|connection refused)' <<<"$hits"; then
    root="The pod cannot reach the cluster DNS service (queries to kube-dns time out / are refused): CoreDNS is down/overloaded or a NetworkPolicy blocks egress to kube-system on port 53."; conf=85
  elif [[ -n $cluster_hosts ]]; then
    root="In-cluster name(s) $(paste -sd, <<<"$cluster_hosts") do not resolve: the target Service does not exist, lives in another namespace (use <svc>.<namespace>.svc.cluster.local), or is misspelled."; conf=85
  elif [[ -n $hosts ]]; then
    root="External name(s) $(paste -sd, <<<"$hosts") do not resolve: upstream DNS/forwarders, private DNS zone association, or egress restrictions."; conf=78
  else
    root="The application fails DNS lookups (see log evidence)."; conf=70
  fi
  local policy; policy=$(pj '.spec.dnsPolicy // "ClusterFirst"')
  [[ $policy == Default || $policy == None ]] && root+=" Note: dnsPolicy=$policy bypasses cluster DNS."
  local target; target=$(head -1 <<<"${cluster_hosts:-$hosts}"); target=${target:-kubernetes.default}
  emit --sev "$(impact_sev)" --title "DNS resolution failure" --root "$root" --conf "$conf" \
    --evidence "$(lines "$hits" "dnsPolicy: $policy")" \
    --recs "$(lines "Verify the target Service exists and has endpoints: kubectl get svc,endpoints -A | grep <name>." \
                    "Check CoreDNS health and logs (kube-system, k8s-app=kube-dns)." \
                    "Check NetworkPolicies allow egress UDP/TCP 53 to kube-system/kube-dns." \
                    "Inspect /etc/resolv.conf in the pod (ndots:5 slows external lookups - use FQDNs with a trailing dot).")" \
    --cmds "$(lines "$CMD_PREFIX run dns-debug --rm -it --restart=Never -n $CTX_NS --image=busybox:1.36 -- nslookup $target" \
                    "$CMD_PREFIX exec $CTX_NAME -n $CTX_NS -- cat /etc/resolv.conf" \
                    "$CMD_PREFIX get pods -n kube-system -l k8s-app=kube-dns -o wide" \
                    "$CMD_PREFIX logs -n kube-system -l k8s-app=kube-dns --tail=50" "$CMD_PREFIX get networkpolicy -n $CTX_NS")"
}

RULE_META[rule_pod_conn_refused]="K8S-NET-002|network|Connection refused"
rule_pod_conn_refused() {
  local hits; hits=$(log_hits "$REFUSED_RE")
  [[ -z $hits ]] && return 0
  local targets descr="" host port localhost=false t first_host="<host>" first_port="<port>"
  targets=$(grep -oE '(dial tcp|ECONNREFUSED|connect to) \[?[A-Za-z0-9.:-]+\]?:[0-9]+' <<<"$hits" | awk '{print $NF}' | tr -d '[]' | awk '!s[$0]++' | head -3)
  while read -r t; do
    [[ -z $t ]] && continue
    host=${t%:*} port=${t##*:}
    [[ $first_host == "<host>" ]] && { first_host=$host; first_port=$port; }
    local svc; svc=$(port_name "$port")
    descr+="${descr:+, }$t${svc:+ ($svc)}"
    [[ $host == 127.0.0.1 || $host == localhost || $host == ::1 ]] && localhost=true
  done <<<"$targets"
  local root conf recs=()
  if [[ $localhost == true ]]; then
    root="The application cannot connect to $descr on localhost: a sidecar it depends on (mesh proxy, cloud-sql-proxy, vault agent...) is not ready/running, or it should use a Service name instead of localhost."; conf=82
    recs=("Start the sidecar first (native sidecars: initContainers with restartPolicy: Always; Istio: holdApplicationUntilProxyStarts)."
          "If the dependency is a separate Service, use its DNS name.")
  else
    root="The application's dependency ${descr:-a dependency} is refusing TCP connections: the target is down, has no ready endpoints behind its Service, or listens on a different port."
    conf=$([[ -n $descr ]] && echo 80 || echo 70)
    recs=("Check the target Service has ready endpoints: kubectl get endpoints <svc> -n <ns>."
          "Verify the Service targetPort matches the backend container port." "Check the health of the dependency itself."
          "Add retry with backoff at startup so transient dependency restarts do not crash the app.")
  fi
  emit --sev "$(impact_sev)" --title "Connection refused to dependency" --root "$root" --conf "$conf" \
    --evidence "$hits" --recs "$(lines "${recs[@]}")" \
    --cmds "$(lines "$CMD_PREFIX get svc,endpoints -n $CTX_NS" "$CMD_PREFIX get endpointslices -n $CTX_NS" \
                    "$CMD_PREFIX exec -it $CTX_NAME -n $CTX_NS -- sh -c 'nc -zv $first_host $first_port'" \
                    "$CMD_PREFIX get networkpolicy -n $CTX_NS")"
}

RULE_META[rule_pod_net_timeout]="K8S-NET-003|network|Network timeout"
rule_pod_net_timeout() {
  local hits; hits=$(log_hits "$TIMEOUT_RE" '*' 20 | grep -viE 'lookup [^ ]+ on|probe' | head -n "$MAX_EVIDENCE")
  [[ -z $hits ]] && return 0
  local t; t=$(grep -oE 'dial tcp [0-9A-Za-z.:-]+:[0-9]+' <<<"$hits" | awk '{print $NF}' | awk '!s[$0]++' | paste -sd, -)
  emit --sev "$(impact_sev MEDIUM LOW)" --title "Network timeout to dependency" --conf 65 \
    --root "Connections to ${t:-a dependency} time out (packets dropped, not refused): NetworkPolicy, security group / firewall, missing route/NAT, or an overloaded target." \
    --evidence "$hits" \
    --recs "$(lines "Review NetworkPolicies (ingress on target, egress on source)." "Check security groups / firewall / NAT for external targets." "Test from a debug pod in the same namespace.")" \
    --cmds "$(lines "$CMD_PREFIX get networkpolicy -n $CTX_NS -o yaml" "$CMD_PREFIX debug -it $CTX_NAME -n $CTX_NS --image=nicolaka/netshoot")"
}

RULE_META[rule_pod_cni]="K8S-NET-004|network|Pod sandbox / CNI failure"
rule_pod_cni() {
  local evs; evs=$( { events_fmt 'FailedCreatePodSandBox|FailedKillPodSandBox'; events_fmt '.*' 'network plugin is not ready|cni plugin not initialized|failed to setup network'; } | awk '!s[$0]++' | tail -3)
  [[ -z $evs ]] && return 0
  local root conf rec
  if grep -qiE 'failed to assign an IP|no available IP|InsufficientFreeAddressesInSubnet|no IP addresses available|range is full' <<<"$evs"; then
    root="The CNI cannot allocate a pod IP: the subnet / IP pool is exhausted (e.g. AWS VPC CNI ENI/IP limits)."; conf=90
    rec="Free IPs or enlarge the pod subnet; enable prefix delegation (AWS VPC CNI) or add secondary CIDRs."
  elif grep -qiE 'network plugin is not ready|cni plugin not initialized|cni config uninitialized' <<<"$evs"; then
    root="The CNI plugin is not running/initialized on the node."; conf=90
    rec="Check the CNI DaemonSet pod (aws-node, calico-node, cilium...) on the node and its logs."
  else
    root="The container runtime failed to create the pod sandbox (network namespace) - see event."; conf=70
    rec="Check kubelet/containerd logs on the node and the CNI DaemonSet health."
  fi
  emit --sev HIGH --title "Pod sandbox / CNI failure" --root "$root" --conf "$conf" \
    --evidence "$(lines "$evs" "Node: $(pj '.spec.nodeName // "-"')")" --recs "$rec" \
    --cmds "$(lines "$(c_describe)" "$CMD_PREFIX get pods -n kube-system -o wide --field-selector spec.nodeName=$(pj '.spec.nodeName // ""')")"
}

# shellcheck shell=bash
# ImagePullBackOff / ErrImagePull / InvalidImageName / ErrImageNeverPull.

RULE_META[rule_pod_imagepull]="K8S-IMG-001|image|Image pull failure"
rule_pod_imagepull() {
  local name rc ready wr wm tr tc lr lc fin img init st
  while IFS=$'\t' read -r name rc ready wr wm tr tc lr lc fin img init st; do
    case $wr in ImagePullBackOff|ErrImagePull|InvalidImageName|ErrImageNeverPull|RegistryUnavailable) ;; *) continue ;; esac
    [[ $img == - ]] && img=$(cspec "$name" '.image')
    local evs text root conf recs=()
    evs=$(events_fmt 'Failed|BackOff|InspectFailed|ErrImageNeverPull' '.' "$name" | tail -3)
    text="$wm $evs"
    if [[ $wr == InvalidImageName ]]; then
      root="The image reference is syntactically invalid."; conf=95
      recs=("Fix the image string (registry/repo:tag or @sha256:digest, lowercase repository).")
    elif [[ $wr == ErrImageNeverPull ]]; then
      root="imagePullPolicy is 'Never' but the image is not present on the node."; conf=95
      recs=("Set imagePullPolicy to IfNotPresent/Always or pre-load the image on all nodes.")
    elif grep -qiE 'manifest unknown|manifest for .* not found|not found: manifest|repository .* not found|name unknown|failed to resolve reference.*not found|: not found' <<<"$text"; then
      root="The image repository or tag does not exist in the registry (typo, tag never pushed, or deleted)."; conf=92
      recs=("Verify the tag exists: skopeo inspect docker://$img" "Check the CI pipeline pushed the tag; prefer immutable tags or digests.")
    elif grep -qiE 'unauthorized|authentication required|pull access denied|denied:|401|403|no basic auth credentials' <<<"$text"; then
      root="The registry rejected the pull: authentication/authorization failed (missing, wrong or expired imagePullSecret, or node IAM role lacks pull permission)."; conf=90
      recs=("Ensure a kubernetes.io/dockerconfigjson imagePullSecret exists in the namespace and is referenced by the pod or its ServiceAccount."
            "Regenerate expired registry credentials (ECR tokens expire after 12h).")
    elif grep -qiE 'toomanyrequests|rate limit' <<<"$text"; then
      root="The registry is rate-limiting pulls (e.g. Docker Hub anonymous limits)."; conf=92
      recs=("Authenticate pulls or mirror images to a private registry / pull-through cache.")
    elif grep -qiE 'x509|certificate' <<<"$text"; then
      root="The node does not trust the registry's TLS certificate."; conf=88
      recs=("Install the registry CA on the nodes (containerd certs.d / hosts.toml) or fix the registry certificate.")
    elif grep -qiE 'no match for platform|no matching manifest' <<<"$text"; then
      root="The image has no variant for the node's CPU architecture/OS."; conf=92
      recs=("Publish a multi-arch image or schedule onto matching nodes (kubernetes.io/arch).")
    elif grep -qiE 'no space left on device' <<<"$text"; then
      root="The node ran out of disk space while pulling the image."; conf=90
      recs=("Free node disk (crictl rmi --prune) or enlarge the node disk.")
    elif grep -qiE 'i/o timeout|dial tcp|no such host|connection refused|deadline exceeded|tls handshake timeout|network is unreachable' <<<"$text"; then
      root="The node cannot reach the registry (DNS, egress firewall/security group, proxy, or registry outage)."; conf=82
      recs=("From the node: crictl pull $img ; curl -v https://<registry>/v2/" "Check NAT/egress rules and HTTP(S)_PROXY / NO_PROXY in the runtime config.")
    else
      root="The kubelet cannot pull the image; see the registry error in the evidence."; conf=60
      recs=("Inspect the pull error in the pod events and test the pull from the node.")
    fi
    local ev=("Container: $name" "Image: $img" "State: Waiting ($wr)")
    [[ $wm != - ]] && ev+=("Message: $wm")
    while IFS= read -r l; do [[ -n $l ]] && ev+=("$l"); done <<<"$evs"
    local ps; ps=$(pj '[.spec.imagePullSecrets[]?.name] | join(" ")')
    [[ -f $CTX/sa.json ]] && ps="$ps $(jq -r '[.imagePullSecrets[]?.name] | join(" ")' "$CTX/sa.json")"
    ps=$(xargs <<<"$ps")
    if [[ -n $ps ]]; then
      ev+=("imagePullSecrets: $ps")
      if [[ -f $CTX/secrets.txt ]]; then
        local s missing=()
        for s in $ps; do grep -qx -- "$s" "$CTX/secrets.txt" || missing+=("$s"); done
        if [[ ${#missing[@]} -gt 0 ]]; then
          ev+=("imagePullSecret(s) MISSING in namespace: ${missing[*]}")
          root+=" Referenced imagePullSecret(s) ${missing[*]} do not exist."; conf=93
          recs=("Create the pull secret: $CMD_PREFIX create secret docker-registry ${missing[0]} -n $CTX_NS --docker-server=<registry> --docker-username=<user> --docker-password=<token>" "${recs[@]}")
        fi
      fi
    else
      ev+=("imagePullSecrets: none (pod and service account)")
    fi
    [[ $img != *@* && ( ${img##*/} != *:* || $img == *:latest ) ]] && recs+=("Avoid the implicit/explicit 'latest' tag; pin a version or digest.")
    emit --sev HIGH --title "Image pull failure ($wr)" --root "$root" --conf "$conf" --container "$name" \
      --evidence "$(lines "${ev[@]}")" --recs "$(lines "${recs[@]}")" \
      --cmds "$(lines "$(c_describe)" "$(c_events)" "skopeo inspect docker://$img   # or: docker manifest inspect $img" \
                      "crictl pull $img   # run on node $(pj '.spec.nodeName // "<node>"')")"
  done < <(statuses_tsv)
}

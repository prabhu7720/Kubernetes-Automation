# shellcheck shell=bash
# TLS / certificate errors in workloads and cert-manager Certificates (cluster scope).

RULE_META[rule_pod_certificates]="K8S-CERT-001|security|TLS certificate error"
rule_pod_certificates() {
  local hits evs
  hits=$(log_hits "$CERT_RE")
  evs=$(events_fmt '.*' 'x509|certificate' | grep -vE '/(Failed|BackOff) ' | tail -2)
  [[ -z $hits && -z $evs ]] && return 0
  local text="$hits $evs" root conf recs=()
  if grep -qiE 'expired|not yet valid|CERT_HAS_EXPIRED' <<<"$text"; then
    root="A TLS certificate in the connection chain has expired (or the node/pod clock is skewed)."; conf=90
    recs=("Renew/rotate the server certificate (check cert-manager Certificate status if used)." "Verify NTP/clock sync if the certificate looks valid.")
  elif grep -qiE 'unknown authority|local issuer|PKIX|self[- ]signed|SELF_SIGNED|UNABLE_TO_VERIFY' <<<"$text"; then
    root="The client does not trust the CA that signed the server certificate (private/internal CA missing from the trust store)."; conf=88
    recs=("Mount the internal CA bundle (trust-manager Bundle / ConfigMap) and point the runtime at it (SSL_CERT_FILE, REQUESTS_CA_BUNDLE, NODE_EXTRA_CA_CERTS, Java truststore)."
          "Never disable verification in production.")
  elif grep -qiE 'valid for|subject alternative names|ALTNAME|hostname mismatch' <<<"$text"; then
    root="The server certificate's SANs do not include the hostname the client connects to."; conf=90
    recs=("Reissue the certificate with the correct DNS SANs or connect via a hostname present in the certificate.")
  elif grep -qiE 'bad certificate|handshake failure' <<<"$text"; then
    root="The TLS handshake fails: mTLS client certificate rejected or protocol/cipher mismatch."; conf=75
    recs=("Verify client certificates (mTLS) and supported TLS versions/ciphers.")
  else
    root="TLS certificate validation fails (see evidence)."; conf=70; recs=("Inspect the certificate chain with openssl.")
  fi
  local host; host=$(grep -oE 'https?://[A-Za-z0-9.-]+\.[a-z]{2,}' <<<"$text" | head -1 | sed -E 's#https?://##')
  host=${host:-<host>}
  emit --sev "$(impact_sev)" --title "TLS certificate error" --root "$root" --conf "$conf" \
    --evidence "$(lines "$hits" "$evs")" --recs "$(lines "${recs[@]}")" \
    --cmds "$(lines "openssl s_client -connect $host:443 -servername $host -showcerts </dev/null | openssl x509 -noout -subject -issuer -dates -ext subjectAltName" \
                    "$CMD_PREFIX get certificates,certificaterequests -n $CTX_NS   # cert-manager" \
                    "$CMD_PREFIX exec $CTX_NAME -n $CTX_NS -- date -u")"
}

RULE_META[rule_cluster_certmanager]="K8S-CERT-002|security|cert-manager Certificate not ready / expiring"
rule_cluster_certmanager() {
  [[ -f $CTX/certificates.json ]] || return 0
  local now; now=$(date -u +%s)
  local ns n ready reason msg notafter secret
  while IFS=$'\t' read -r ns n ready reason msg notafter secret; do
    local exp=""; [[ $notafter != - ]] && exp=$(date -u -d "$notafter" +%s 2>/dev/null)
    local res="Certificate $ns/$n"
    local ev; ev=$(lines "Certificate $ns/$n: Ready=$ready reason=$reason" "Message: $msg" "notAfter: $notafter" "secretName: $secret")
    local cmds; cmds=$(lines "$CMD_PREFIX describe certificate $n -n $ns" "$CMD_PREFIX get certificaterequests,orders,challenges -n $ns" \
                             "$CMD_PREFIX logs -n cert-manager deploy/cert-manager --tail=100")
    if [[ -n $exp && $exp -lt $now ]]; then
      emit --sev CRITICAL --title "Certificate expired" --resource "$res" --conf 97 --root "Certificate $ns/$n expired at $notafter." \
        --evidence "$ev" --recs "Fix the issuance failure and force renewal: cmctl renew $n -n $ns" --cmds "$cmds"
    elif [[ $ready == False ]]; then
      emit --sev HIGH --title "Certificate not ready" --resource "$res" --conf 90 --root "cert-manager cannot issue/renew $ns/$n: $msg" \
        --evidence "$ev" --recs "Check the Issuer/ClusterIssuer status and ACME challenges (DNS01/HTTP01 reachability, credentials)." --cmds "$cmds"
    elif [[ -n $exp && $(( (exp - now) / 86400 )) -lt $CERT_EXPIRY_WARN_DAYS ]]; then
      emit --sev MEDIUM --title "Certificate expiring soon" --resource "$res" --conf 85 \
        --root "Certificate $ns/$n expires in $(( (exp - now) / 86400 )) day(s) and has not been renewed." \
        --evidence "$ev" --recs "Verify renewal is progressing (renewBefore) and the issuer is healthy." --cmds "$cmds"
    fi
  done < <(jq -r '.items[] | ([.status.conditions[]? | select(.type == "Ready")][0]) as $c
           | [.metadata.namespace, .metadata.name, ($c.status // "-"), ($c.reason // "-"), (($c.message // "-") | gsub("[\t\n]"; " ")),
              (.status.notAfter // "-"), (.spec.secretName // "-")] | @tsv' "$CTX/certificates.json")
}

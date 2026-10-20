#!/usr/bin/env bash
# End-to-end tests for k8s-rca.sh against the synthetic cluster (tests/fake_kubectl.py).
# Usage: tests/run_tests.sh        (needs bash 4+, jq, python3)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
export KUBECTL="python3 $HERE/fake_kubectl.py"
AGENT="$ROOT/k8s-rca.sh"
pass=0 fail=0

check() { # name condition-description command...
  local name=$1; shift
  if "$@"; then pass=$((pass + 1)); echo "PASS $name"; else fail=$((fail + 1)); echo "FAIL $name"; fi
}
has() { grep -q -- "$2" <<<"$1"; }

out=$("$AGENT" analyze pod checkout-api-768bb9ff95-abcde -n payments --no-facts 2>&1); rc=$?
check "pod: OOM detected"              has "$out" "K8S-OOM-001"
check "pod: confidence 95%"            has "$out" "95%"
check "pod: crashloop marked symptom"  has "$out" "CrashLoopBackOff (symptom)"
check "pod: exit code 1 on HIGH"       test "$rc" -eq 1

out=$("$AGENT" analyze pod checkout-api-768bb9ff95-fghij -n payments 2>&1)
check "pod: DNS failure"               has "$out" "K8S-NET-001"
check "pod: connection refused"        has "$out" "10.0.3.15:5432 (PostgreSQL)"
check "pod: secrets redacted"          bash -c '! grep -q SuperSecret123 <<<"$0"' "$out"

json=$("$AGENT" analyze namespace payments -o json 2>/dev/null)
check "ns: valid json"                 jq -e . <<<"$json" >/dev/null
for id in K8S-IMG-001 K8S-SCHED-001 K8S-CFG-003 K8S-CFG-001 K8S-PROBE-001 K8S-PROBE-002 K8S-DEPLOY-001 K8S-STOR-002 K8S-NODE-001; do
  check "ns: $id" jq -e --arg id "$id" '[.resources[].findings[].rule_id] | index($id) != null' <<<"$json" >/dev/null
done
check "ns: secret correlation"         jq -e '[.resources[].findings[] | select(.rule_id == "K8S-CFG-001")][0].is_symptom' <<<"$json" >/dev/null

out=$("$AGENT" analyze cluster 2>&1)
check "cluster: CoreDNS"               has "$out" "kube-system component unhealthy: kube-dns"
check "cluster: node NotReady"         has "$out" "CRITICAL | Node NotReady"

md=$("$AGENT" analyze deployment checkout-api -n payments -o markdown 2>&1)
check "deployment: markdown"           has "$md" "# Kubernetes Root Cause Analysis Report"
check "deployment: rollout stuck"      has "$md" "Rollout stuck"

"$AGENT" analyze pod nope -n payments >/dev/null 2>&1; rc=$?
check "missing pod -> exit 2"          test "$rc" -eq 2

"$AGENT" analyze pod checkout-api-768bb9ff95-klmno -n payments >/dev/null 2>&1; rc=$?
check "healthy pod -> exit 0"          test "$rc" -eq 0

cfg=$(mktemp); cp "$ROOT/config/agent.conf" "$cfg"; echo 'DISABLED_RULES=(K8S-OOM-001)' >>"$cfg"
out=$("$AGENT" analyze pod checkout-api-768bb9ff95-abcde -n payments --config "$cfg" 2>&1)
check "disabled rule honoured"         bash -c '! grep -q "K8S-OOM-001" <<<"$0"' "$out"

plug=$(mktemp -d); cat >"$plug/custom.sh" <<'EOF'
RULE_META[rule_pod_custom_test]="CUSTOM-001|test|Custom test rule"
rule_pod_custom_test() { emit --sev LOW --title "custom" --root "plugin works" --conf 99; }
EOF
cp "$ROOT/config/agent.conf" "$cfg"; echo "EXTRA_RULE_DIRS=($plug)" >>"$cfg"
out=$("$AGENT" analyze pod checkout-api-768bb9ff95-klmno -n payments --config "$cfg" 2>&1)
check "drop-in plugin rule"            has "$out" "CUSTOM-001"
rm -rf "$cfg" "$plug"

echo "$pass passed, $fail failed"
[[ $fail -eq 0 ]]

#!/usr/bin/env bash
# =============================================================================
# k8s-rca.sh - Kubernetes Root Cause Analysis agent (Bash edition)
#
#   ./k8s-rca.sh analyze pod <pod> -n <namespace>
#   ./k8s-rca.sh analyze deployment <deployment> -n <namespace>
#   ./k8s-rca.sh analyze namespace <namespace>
#   ./k8s-rca.sh analyze node <node>
#   ./k8s-rca.sh analyze cluster
#   ./k8s-rca.sh rules list
#
# Options:
#   --kubeconfig PATH     kubeconfig file (default: kubectl's normal resolution)
#   --context NAME        kubeconfig context
#   -o text|markdown|json output format (default text)
#   --output-file FILE    also write the report to FILE
#   --min-severity LEVEL  hide findings below LEVEL (info|low|medium|high|critical)
#   --fail-on LEVEL       exit 1 if any finding >= LEVEL (default high)
#   --tail N              log lines per container        --max-pods N
#   --no-logs --no-metrics --no-facts --keep-workdir -v --config FILE -h
#
# Requires: bash >= 4, kubectl, jq, GNU coreutils/sed/awk/grep.
# Privacy:  read-only kubectl only; no data is sent anywhere except the kubectl
#           calls to the API server in your kubeconfig. No curl/wget is used.
# Exit:     0 nothing >= --fail-on | 1 findings >= --fail-on | 2 error
# =============================================================================
VERSION="1.0.0"
AGENT_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ${BASH_VERSINFO[0]} -lt 4 ]]; then
  echo "error: bash >= 4 required (macOS: brew install bash)" >&2; exit 2
fi

# shellcheck source=lib/common.sh
source "$AGENT_HOME/lib/common.sh"
# shellcheck source=lib/engine.sh
source "$AGENT_HOME/lib/engine.sh"
# shellcheck source=lib/collectors.sh
source "$AGENT_HOME/lib/collectors.sh"
# shellcheck source=lib/analyzers.sh
source "$AGENT_HOME/lib/analyzers.sh"

usage() { sed -n '3,27p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

# ------------------------------------------------------------------ defaults + config
CONFIG_FILE="${K8S_RCA_CONFIG:-$AGENT_HOME/config/agent.conf}"
for ((i = 1; i <= $#; i++)); do [[ ${!i} == --config ]] && { j=$((i + 1)); CONFIG_FILE=${!j}; }; done
[[ -f $CONFIG_FILE ]] || die "config file not found: $CONFIG_FILE"
# shellcheck source=config/agent.conf
source "$CONFIG_FILE"

FORMAT=text OUTPUT_FILE="" MIN_SEVERITY=INFO FAIL_ON=HIGH SHOW_FACTS=true KEEP_WORK=false VERBOSE=0
KCONFIG="" KCONTEXT="" NAMESPACE=default
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case $1 in
    -n|--namespace) NAMESPACE=$2; shift 2 ;;
    --kubeconfig) KCONFIG=$2; shift 2 ;;
    --context) KCONTEXT=$2; shift 2 ;;
    -o|--output) FORMAT=$2; shift 2 ;;
    --output-file) OUTPUT_FILE=$2; shift 2 ;;
    --min-severity) MIN_SEVERITY=${2^^}; shift 2 ;;
    --fail-on) FAIL_ON=${2^^}; shift 2 ;;
    --tail) LOG_TAIL=$2; shift 2 ;;
    --max-pods) MAX_PODS=$2; shift 2 ;;
    --request-timeout) REQUEST_TIMEOUT=$2; shift 2 ;;
    --config) shift 2 ;;
    --no-logs) COLLECT_LOGS=false; shift ;;
    --no-metrics) COLLECT_METRICS=false; shift ;;
    --no-facts) SHOW_FACTS=false; shift ;;
    --keep-workdir) KEEP_WORK=true; shift ;;
    -v|--verbose) VERBOSE=$((VERBOSE + 1)); shift ;;
    -h|--help) usage 0 ;;
    --version) echo "k8s-rca.sh $VERSION"; exit 0 ;;
    -*) die "unknown option: $1 (see --help)" ;;
    *) POSITIONAL+=("$1"); shift ;;
  esac
done

case $FORMAT in text|markdown|json) ;; *) die "invalid output format: $FORMAT" ;; esac
[[ $(sev_num "$MIN_SEVERITY") -ge 0 ]] || die "invalid --min-severity: $MIN_SEVERITY"
[[ $(sev_num "$FAIL_ON") -ge 0 ]] || die "invalid --fail-on: $FAIL_ON"
[[ ${#POSITIONAL[@]} -ge 1 ]] || usage 2

need jq
# KUBECTL may be overridden (e.g. KUBECTL="python3 tests/fake_kubectl.py" for the offline demo)
read -r -a KUBECTL_CMD <<<"${KUBECTL:-kubectl}"
need "${KUBECTL_CMD[0]}"
KFLAGS=()
[[ -n $KCONFIG ]] && { [[ -f $KCONFIG ]] || die "kubeconfig not found: $KCONFIG"; KFLAGS+=(--kubeconfig "$KCONFIG"); }
[[ -n $KCONTEXT ]] && KFLAGS+=(--context "$KCONTEXT")
CMD_PREFIX="kubectl${KCONFIG:+ --kubeconfig $KCONFIG}${KCONTEXT:+ --context $KCONTEXT}"

WORK=$(mktemp -d "${TMPDIR:-/tmp}/k8s-rca.XXXXXX") || die "cannot create work dir"
chmod 700 "$WORK"
mkdir -p "$WORK/cache" "$WORK/ctx"
: >"$WORK/resources.jsonl"; : >"$WORK/facts.jsonl"; : >"$WORK/findings.jsonl"; : >"$WORK/errors.jsonl"
cleanup() { if [[ $KEEP_WORK == true ]]; then echo "work dir kept: $WORK" >&2; else rm -rf "$WORK"; fi; }
trap cleanup EXIT
trap 'echo "interrupted" >&2; exit 130' INT TERM

load_rules

# ------------------------------------------------------------------ dispatch
cmd=${POSITIONAL[0]}
target=${POSITIONAL[1]:-}
name=${POSITIONAL[2]:-}
case $cmd in
  rules)
    [[ $target == list ]] || usage 2
    list_rules; exit 0 ;;
  analyze)
    case $target in
      pod)        [[ -n $name ]] || die "pod name required"; analyze_pod "$NAMESPACE" "$name" "" ;;
      deployment) [[ -n $name ]] || die "deployment name required"; analyze_deployment "$NAMESPACE" "$name" "" ;;
      namespace)  analyze_namespace "${name:-$NAMESPACE}" ;;
      node)       [[ -n $name ]] || die "node name required"; analyze_node_full "$name" ;;
      cluster)    analyze_cluster ;;
      *) die "unknown target '$target' (pod|deployment|namespace|node|cluster)" ;;
    esac ;;
  *) usage 2 ;;
esac

# ------------------------------------------------------------------ report
CTX_LABEL=${KCONTEXT:-$(kube config current-context 2>/dev/null || echo unknown)}
render() { # fmt
  jq -rn --slurpfile R "$WORK/resources.jsonl" --slurpfile F "$WORK/facts.jsonl" \
         --slurpfile X "$WORK/findings.jsonl" --slurpfile E "$WORK/errors.jsonl" \
         --arg fmt "$1" --arg minsev "$MIN_SEVERITY" --arg generated "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
         --arg context "$CTX_LABEL" --arg version "$VERSION" --arg showfacts "$SHOW_FACTS" \
         -f "$AGENT_HOME/lib/report.jq"
}
report=$(render "$FORMAT") || die "report rendering failed"
printf '%s\n' "$report"
if [[ -n $OUTPUT_FILE ]]; then
  printf '%s\n' "$report" >"$OUTPUT_FILE" && echo "Report written to $OUTPUT_FILE" >&2
fi

worst=$(MIN_SEVERITY=INFO render maxsev)
[[ $worst -ge $(sev_num "$FAIL_ON") ]] && exit 1
exit 0

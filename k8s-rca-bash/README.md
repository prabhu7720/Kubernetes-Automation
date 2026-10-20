# k8s-rca.sh: Kubernetes Root Cause Analysis (Bash edition)

This is a rule-based diagnostic agent written in Bash. It uses `kubectl` and `jq` with your existing kubeconfig. Logs, events, specs and secrets are never sent to an LLM or any external API, and the script never calls `curl` or `wget`.

## Requirements
- bash 4+ (Linux, WSL, or Git Bash; macOS needs `brew install bash`)
- kubectl and jq 1.6+
- GNU sed, awk and grep

## Usage
```bash
./k8s-rca.sh analyze pod <pod> -n <namespace>
./k8s-rca.sh analyze deployment <deployment> -n <namespace>
./k8s-rca.sh analyze namespace <namespace>
./k8s-rca.sh analyze node <node>
./k8s-rca.sh analyze cluster
./k8s-rca.sh rules list
```

Options:

| Option | Purpose |
|---|---|
| `--kubeconfig PATH` | kubeconfig file to use |
| `--context NAME` | kubeconfig context to use |
| `-o text\|markdown\|json` | output format |
| `--output-file FILE` | also write the report to a file |
| `--min-severity LEVEL` | hide findings below this severity |
| `--fail-on LEVEL` | severity that makes the script exit 1 |
| `--tail N` | log lines fetched per container |
| `--max-pods N` | maximum pods analyzed in deployment, namespace and cluster modes |
| `--no-logs` | skip container logs |
| `--no-metrics` | skip `kubectl top` |
| `--no-facts` | omit the facts section from the report |
| `--keep-workdir` | keep the temporary collection directory |
| `-v` | verbose logging |
| `--config FILE` | use another settings file |

Exit codes: `0` means no findings at or above `--fail-on`, `1` means there are findings at or above `--fail-on`, and `2` means an error.

Offline demo and tests:
```bash
KUBECTL="python3 tests/fake_kubectl.py" ./k8s-rca.sh analyze namespace payments
tests/run_tests.sh
```

## Layout
```
k8s-rca.sh            CLI: args, config, dispatch, report rendering, exit code
lib/common.sh         read-only kubectl wrapper, JSONL writers, context accessors, redaction, quantities
lib/collectors.sh     collect_pod / deployment / namespace / cluster / node into per-resource context dirs
lib/engine.sh         rule discovery (rule_<scope>_* functions), run_rules, emit, rules list
lib/analyzers.sh      orchestration per mode + fact summaries + unhealthy-pod triage
lib/report.jq         text / markdown / json rendering, de-duplication, correlation, sorting
rules/*.sh            diagnostic rules (drop-in plugins); rules/_helpers.sh = shared helpers
config/agent.conf     thresholds, limits, disabled rules, extra rule dirs, severity overrides
deploy/rbac-readonly.yaml  least-privilege ClusterRole
tests/                fake_kubectl.py + fixtures + run_tests.sh
```

## Adding a rule

Create `rules/my_rule.sh`, or put it in a directory listed in `EXTRA_RULE_DIRS`:

```bash
RULE_META[rule_pod_long_grace]="CUSTOM-001|workload|Long termination grace period"
rule_pod_long_grace() {
  local g; g=$(pj '.spec.terminationGracePeriodSeconds // 30')
  [[ $g -gt 300 ]] || return 0
  emit --sev LOW --title "Long termination grace period" --conf 90 \
       --root "terminationGracePeriodSeconds=$g slows rollouts and drains." \
       --evidence "terminationGracePeriodSeconds: $g" \
       --recs "Lower the grace period and handle SIGTERM promptly." \
       --cmds "$CMD_PREFIX get pod $CTX_NAME -n $CTX_NS -o yaml"
}
```

- The function name sets the scope: `rule_pod_`, `rule_deployment_`, `rule_node_`, `rule_namespace_`, `rule_cluster_` or `rule_all_`.
- Rules can use these context helpers: `pj`, `statuses_tsv`, `cspec`, `events_fmt`, `event_count`, `log_hits`, `pod_ready` and `impact_sev`.

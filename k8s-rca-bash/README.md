# k8s-rca.sh: Kubernetes Root Cause Analysis (Bash edition)

`k8s-rca.sh` diagnoses failing Kubernetes workloads from the command line. It connects with your **existing kubeconfig** and collects the evidence an SRE would gather by hand: pod status, describe output, previous and current logs, events, owner deployment, limits, node, PVCs and service account. It then runs that evidence through a **local, rule-based engine** and prints a root cause analysis report.

Every finding in the report has:

- **Severity**
- **Evidence**
- **Root cause**
- **Confidence score**
- **Recommended fix**
- **Validation commands**

> **No cluster data leaves your machine.** No LLM, SaaS or external API is called, and the script never uses `curl` or `wget`. The only network traffic is `kubectl` talking to the API server in your kubeconfig.

---

## Table of contents

1. [What it detects](#1-what-it-detects)
2. [Requirements and installation](#2-requirements-and-installation)
3. [Quick start](#3-quick-start)
4. [Commands](#4-commands)
5. [Options reference](#5-options-reference)
6. [Environment variables](#6-environment-variables)
7. [Reading the report](#7-reading-the-report)
8. [Output formats and saving reports](#8-output-formats-and-saving-reports)
9. [Exit codes and CI/CD integration](#9-exit-codes-and-cicd-integration)
10. [Scheduling and multi-cluster usage](#10-scheduling-and-multi-cluster-usage)
11. [Configuration file](#11-configuration-file)
12. [Permissions (RBAC)](#12-permissions-rbac)
13. [Security and data privacy](#13-security-and-data-privacy)
14. [Writing your own rules](#14-writing-your-own-rules)
15. [Offline demo and tests](#15-offline-demo-and-tests)
16. [How it works](#16-how-it-works)
17. [Performance tips](#17-performance-tips)
18. [Troubleshooting](#18-troubleshooting)
19. [Limitations](#19-limitations)

---

## 1. What it detects

| Rule ID | Detects |
|---|---|
| `K8S-OOM-001` | OOMKilled / exit 137, limit vs request, JVM / Node.js / Go / Python heap OOM in logs |
| `K8S-CRASH-001` | CrashLoopBackOff with exit-code meaning and log signatures. Marked as a symptom when caused by OOM, liveness kills or dependency failures |
| `K8S-CRASH-002` | Frequent restarts (≥ `RESTART_THRESHOLD`) |
| `K8S-CRASH-003` | Containers terminated with an error (Jobs, `restartPolicy: Never`) |
| `K8S-IMG-001` | ImagePullBackOff / ErrImagePull / InvalidImageName / ErrImageNeverPull: tag not found, auth, rate limit, TLS, platform, disk, network, missing pull secrets |
| `K8S-CFG-001` | CreateContainerConfigError: missing secret / configmap / key, runAsNonRoot conflict |
| `K8S-CFG-002` | CreateContainerError / RunContainerError: bad entrypoint, mount type mismatch, exec format error |
| `K8S-CFG-003` | Referenced **Secret missing** (proactive check of every reference) |
| `K8S-CFG-004` | Referenced **ConfigMap missing** |
| `K8S-STOR-001` | FailedMount / FailedAttachVolume: Multi-Attach, CSI driver, NFS, permissions, attach limits |
| `K8S-STOR-002` | PVC missing / Pending / Lost, StorageClass missing, PV Failed / Released |
| `K8S-SCHED-001` | FailedScheduling, parsed per reason: Insufficient cpu/memory, taints, affinity, spread, PVC, cordoned, max pods |
| `K8S-NET-001` | DNS failures (in-cluster name vs external name vs kube-dns unreachable) |
| `K8S-NET-002` | Connection refused (target host:port, well-known service, localhost sidecar case) |
| `K8S-NET-003` | Network timeouts (NetworkPolicy / firewall / NAT) |
| `K8S-NET-004` | Pod sandbox / CNI failures, IP exhaustion |
| `K8S-PROBE-001/002/003` | Readiness / liveness / startup probe failures (HTTP code, refused, timeout, scheme, wrong port) |
| `K8S-RES-001` | Usage near memory limit, CPU throttling, no requests / limits |
| `K8S-RES-002` | ResourceQuota / LimitRange exhaustion |
| `K8S-NODE-001` | Node NotReady (kubelet down, runtime, PLEG, CNI, certificates) |
| `K8S-NODE-002` | Node Memory / Disk / PID pressure, NetworkUnavailable |
| `K8S-NODE-003` | Pod evicted / preempted |
| `K8S-CERT-001` | TLS / x509 errors in logs (expired, unknown CA, SAN mismatch, mTLS) |
| `K8S-CERT-002` | cert-manager Certificates not ready / expiring / expired |
| `K8S-RBAC-001` | RBAC "forbidden" errors (parsed user, verb and resource, with a fix command), cloud IAM denials, service account token not mounted |
| `K8S-RBAC-002` | ServiceAccount missing |
| `K8S-RBAC-003` | The agent itself lacks read permission (analysis incomplete) |
| `K8S-DEPLOY-001` | Rollout stuck (ProgressDeadlineExceeded) with the image diff vs the previous revision |
| `K8S-DEPLOY-002` | ReplicaSet cannot create pods (PodSecurity, admission webhook, missing SA) |
| `K8S-DEPLOY-003` | Unavailable replicas / paused rollout |
| `K8S-NS-001/002` | Namespace stuck Terminating, Pending PVCs |
| `K8S-CLUS-001` | Unhealthy kube-system components (CoreDNS escalated to Critical) |

Run `./k8s-rca.sh rules list` to see the rules that are actually loaded, including any custom ones.

---

## 2. Requirements and installation

| Requirement | Version | Notes |
|---|---|---|
| bash | 4.0+ | Associative arrays are required. macOS ships 3.2. |
| kubectl | within ±1 minor of the cluster | Must already work with your kubeconfig |
| jq | 1.6+ | Used for all JSON processing |
| GNU sed / awk / grep / coreutils | any recent | BSD variants (macOS) are not supported |
| python3 | 3.x | **Only** for the offline demo / tests (`tests/fake_kubectl.py`) |

### Linux (RHEL / Amazon Linux / Ubuntu bastion)

```bash
# jq
sudo dnf install -y jq        # RHEL / Amazon Linux 2023
sudo apt-get install -y jq    # Ubuntu / Debian

# install the tool
sudo mkdir -p /opt/k8s-rca
sudo cp -r k8s-rca-bash/* /opt/k8s-rca/
sudo chmod +x /opt/k8s-rca/k8s-rca.sh /opt/k8s-rca/tests/run_tests.sh
sudo ln -sf /opt/k8s-rca/k8s-rca.sh /usr/local/bin/k8s-rca

k8s-rca --version
k8s-rca rules list
```

> Air-gapped hosts: copy the folder over and install `jq` from your internal repository. Nothing else is downloaded at runtime.

### Windows: WSL (recommended)

```bash
# inside WSL (Ubuntu)
sudo apt-get update && sudo apt-get install -y jq
# reuse your Windows kubeconfig if you don't have one in WSL:
export KUBECONFIG=/mnt/c/Users/<you>/.kube/config
cd /mnt/c/Users/<you>/github/Kubernetes-Automation/k8s-rca-bash
chmod +x k8s-rca.sh
./k8s-rca.sh rules list
```

### Windows: Git Bash

```bash
winget install jqlang.jq          # from PowerShell, then reopen Git Bash
cd ~/github/Kubernetes-Automation/k8s-rca-bash
./k8s-rca.sh rules list
```

> If you cloned on Windows and see `$'\r': command not found`, the files were converted to CRLF line endings. Fix them with `git config core.autocrlf input` and re-checkout, or run `sed -i 's/\r$//' k8s-rca.sh lib/*.sh rules/*.sh config/agent.conf`.

### macOS

```bash
brew install bash jq gnu-sed grep coreutils gawk
# put the GNU tools first on PATH for this tool:
export PATH="$(brew --prefix)/opt/gnu-sed/libexec/gnubin:$(brew --prefix)/opt/grep/libexec/gnubin:$(brew --prefix)/opt/coreutils/libexec/gnubin:$PATH"
$(brew --prefix)/bin/bash ./k8s-rca.sh rules list
```

### Verify the installation

```bash
./k8s-rca.sh --version          # k8s-rca.sh 1.0.0
./k8s-rca.sh rules list         # should list ~38 rule functions
kubectl auth can-i list pods -A # confirms your kubeconfig works
tests/run_tests.sh              # optional, offline, needs python3
```

---

## 3. Quick start

```bash
# 1. Make sure kubectl points at the right cluster
kubectl config current-context

# 2. Find something broken
kubectl get pods -A | grep -Ev 'Running|Completed'

# 3. Analyze it
./k8s-rca.sh analyze pod checkout-api-768bb9ff95-abcde -n payments

# 4. Or analyze the whole service / namespace
./k8s-rca.sh analyze deployment checkout-api -n payments
./k8s-rca.sh analyze namespace payments
```

Try it without a cluster:

```bash
KUBECTL="python3 tests/fake_kubectl.py" ./k8s-rca.sh analyze namespace payments
```

---

## 4. Commands

```
./k8s-rca.sh analyze pod <pod-name> [-n <namespace>] [options]
./k8s-rca.sh analyze deployment <deployment-name> [-n <namespace>] [options]
./k8s-rca.sh analyze namespace <namespace> [options]
./k8s-rca.sh analyze node <node-name> [options]
./k8s-rca.sh analyze cluster [options]
./k8s-rca.sh rules list
```

If you omit `-n`, the `default` namespace is used.

### 4.1 `analyze pod`

Full evidence collection for **one pod**, then all pod rules.

| Collected | kubectl call |
|---|---|
| Pod status, container states, restart counts, last termination | `get pod -o json` |
| Events for the pod | `get events --field-selector involvedObject.kind=Pod,involvedObject.name=<pod>` |
| Current logs (each container that has run) | `logs -c <c> --tail=N` |
| Previous logs (only if the container restarted) | `logs -c <c> --tail=N --previous` |
| Owner ReplicaSet and Deployment | `get replicaset`, `get deployment` |
| Node and its conditions | `get node <nodeName>` |
| PVC → PV → StorageClass, plus PVC events | `get pvc`, `get pv`, `get storageclass`, `get events` |
| Service account | `get serviceaccount` |
| Secret / ConfigMap **names** (only if referenced) | `get secrets --no-headers`, `get configmaps --no-headers` |
| Live CPU / memory usage (optional) | `top pod --containers` |

```bash
./k8s-rca.sh analyze pod orders-worker-6d9f7c-x1y2z -n payments
./k8s-rca.sh analyze pod coredns-5d78c9869d-bbbbb -n kube-system --tail 1000
```

### 4.2 `analyze deployment`

Checks rollout state, replica-creation failures, availability and quota. It then drills into the most unhealthy pods of that deployment (up to `--max-pods`), ranked by a health score:

- **Highest:** waiting errors, evictions, failed phases, non-zero exit codes and OOMKills.
- **Then:** pods that are not Ready and pods with many restarts.

```bash
./k8s-rca.sh analyze deployment checkout-api -n payments
./k8s-rca.sh analyze deployment checkout-api -n payments --max-pods 3 -o markdown --output-file rca.md
```

### 4.3 `analyze namespace`

Reads every pod, deployment, ReplicaSet, PVC, quota and event in the namespace in one list call per type. It then:

1. Runs the namespace rules: Terminating namespace, Pending PVCs, quotas.
2. Analyzes the failing pods and groups them under their owning Deployment.

```bash
./k8s-rca.sh analyze namespace payments
./k8s-rca.sh analyze namespace payments --min-severity medium --no-facts
```

### 4.4 `analyze node`

Node conditions (Ready, pressure), node events, then the unhealthy pods scheduled on that node.

```bash
./k8s-rca.sh analyze node ip-10-0-3-30.ec2.internal
```

### 4.5 `analyze cluster`

1. Checks every node.
2. Checks kube-system component health, with CoreDNS problems escalated.
3. Checks cert-manager Certificates, if cert-manager is installed.
4. Analyzes the worst unhealthy pods across **all** namespaces (up to `--max-pods`).

```bash
./k8s-rca.sh analyze cluster --context prod-east
./k8s-rca.sh analyze cluster --max-pods 10 --min-severity high
```

### 4.6 `rules list`

Lists every loaded rule function with its ID, scope and category. Use it to confirm a custom rule was picked up.

---

## 5. Options reference

Options can appear anywhere after the command.

| Option | Default | Description |
|---|---|---|
| `-n, --namespace NS` | `default` | Namespace for `pod` / `deployment` (and `namespace` if no name is given) |
| `--kubeconfig PATH` | kubectl default (`$KUBECONFIG` or `~/.kube/config`) | kubeconfig file to use |
| `--context NAME` | current-context | kubeconfig context to use |
| `-o, --output FORMAT` | `text` | `text`, `markdown` or `json` |
| `--output-file FILE` | — | Also write the report to `FILE` (still printed to stdout) |
| `--min-severity LEVEL` | `info` | Hide findings below `info\|low\|medium\|high\|critical` |
| `--fail-on LEVEL` | `high` | Exit code `1` if any finding is ≥ `LEVEL` |
| `--tail N` | `500` | Log lines fetched per container (current and previous) |
| `--max-pods N` | `25` | Max pods drilled into in deployment / namespace / node / cluster mode |
| `--request-timeout SEC` | `30` | Passed to `kubectl --request-timeout` |
| `--no-logs` | off | Skip container logs (faster; log-based rules are skipped) |
| `--no-metrics` | off | Skip `kubectl top` (use when metrics-server is absent or slow) |
| `--no-facts` | off | Omit the "Findings" fact summary from the report |
| `--keep-workdir` | off | Keep the temporary collection directory and print its path (debugging) |
| `--config FILE` | `config/agent.conf` | Use another configuration file |
| `-v, --verbose` | off | Log progress and each rule to stderr (`-vv` for more) |
| `--version` | — | Print the version |
| `-h, --help` | — | Show usage |

---

## 6. Environment variables

| Variable | Purpose | Example |
|---|---|---|
| `KUBECONFIG` | Standard kubectl variable; honoured automatically | `export KUBECONFIG=~/.kube/prod.yaml` |
| `KUBECTL` | Command used instead of `kubectl` (can include arguments) | `KUBECTL=/opt/bin/kubectl-1.31` or `KUBECTL="python3 tests/fake_kubectl.py"` |
| `K8S_RCA_CONFIG` | Default configuration file (overridden by `--config`) | `K8S_RCA_CONFIG=/etc/k8s-rca/agent.conf` |
| `TMPDIR` | Where the temporary work directory is created | `TMPDIR=/var/tmp` |

---

## 7. Reading the report

```
====================================================
KUBERNETES ROOT CAUSE ANALYSIS REPORT
====================================================
Generated: 2026-10-20T13:16:04Z   Agent: k8s-rca.sh v1.0.0
Cluster context: prod-east
Analysis engine: local rule-based (bash + kubectl + jq, no external APIs / LLMs)

Resource:
  Pod payments/checkout-api-768bb9ff95-abcde        <- what was analyzed

Severity:
  High                                              <- worst finding (incl. child resources)

Primary Root Cause:                                 <- the top finding that is NOT a symptom
  Container OOMKilled: Container 'app' exceeded its configured memory limit (512Mi) ...

Findings:                                           <- neutral facts (hide with --no-facts)
  - Phase: Running (0/1 containers ready)
  - Restart count: 37
  - container app: waiting (CrashLoopBackOff), restarts=37, last termination: OOMKilled (exit 137)
      app resources: requests cpu=100m memory=256Mi | limits cpu=500m memory=512Mi
  - Owner: Deployment/checkout-api <- ReplicaSet/checkout-api-768bb9ff95
  - Node: ip-10-0-1-10 (Ready; no pressure conditions)

Issues Detected: 2
----------------------------------------------------
[1] HIGH | Container OOMKilled | K8S-OOM-001 | container: app
----------------------------------------------------
Severity:            High
Root Cause:          what is wrong and why
Evidence:            exit code, termination reason, limits, matching log lines, events
Confidence:          95%
Recommended Actions: numbered fixes
Validation Commands: kubectl commands with the real names filled in
----------------------------------------------------
[2] HIGH | CrashLoopBackOff (symptom) | K8S-CRASH-001 | container: app
...
```

How to read it:

- **Severity:**
  - **Critical:** service down or data at risk.
  - **High:** the workload is failing.
  - **Medium:** degraded or at risk.
  - **Low:** hygiene problem.
  - **Info:** context only.
- **Confidence:**
  - **90–98%:** an explicit API reason, such as `OOMKilled` or `secret "x" not found`.
  - **75–89%:** a specific log or event pattern.
  - **50–74%:** an inferred cause. Verify these with the validation commands.
- **(symptom):** a consequence of another finding. Fix the root cause first. For example, CrashLoopBackOff caused by OOMKilled, or "unavailable replicas" caused by failing pods.
- **Related Findings:** findings about the same object (for example, the same missing secret reported by two rules) are linked. The strongest one is primary.
- **Collection Warnings:** steps that could not be collected, usually because of RBAC. Those checks were skipped.
- **Multi-resource runs** (deployment / namespace / node / cluster) add a **RESOURCE SUMMARY** tree and then a section per affected resource:

```
RESOURCE SUMMARY
- [High] Deployment payments/checkout-api: Container OOMKilled
  - [High] Pod payments/checkout-api-768bb9ff95-abcde: Container OOMKilled
  - [High] Pod payments/checkout-api-768bb9ff95-fghij: DNS resolution failure
- [High] Pod payments/orders-worker-6d9f7c-x1y2z: Secret missing
```

---

## 8. Output formats and saving reports

```bash
# Text (default) - terminal
./k8s-rca.sh analyze deployment checkout-api -n payments

# Markdown - paste into Jira / ServiceNow / Confluence / GitHub issues
./k8s-rca.sh analyze deployment checkout-api -n payments -o markdown --output-file rca-checkout.md

# JSON - automation
./k8s-rca.sh analyze namespace payments -o json --output-file rca.json
```

The JSON structure looks like this:

```json
{
  "metadata":  { "generated_at": "...", "agent": "k8s-rca.sh", "version": "1.0.0", "context": "prod-east", "engine": "..." },
  "summary":   { "severity": "High", "issues": 18, "primary_root_cause": { "rule_id": "K8S-CFG-003", "...": "..." } },
  "resources": [
    { "key": "Pod payments/x", "kind": "Pod", "name": "x", "namespace": "payments", "parent": "Deployment payments/y",
      "severity": "High", "facts": ["..."], "errors": ["..."],
      "findings": [ { "rule_id", "title", "severity", "resource", "container", "root_cause", "evidence": [],
                      "confidence", "recommendations": [], "commands": [], "is_symptom", "related": [] } ] }
  ]
}
```

Useful `jq` one-liners:

```bash
# one line per finding: severity, rule, resource, title
./k8s-rca.sh analyze namespace payments -o json 2>/dev/null \
  | jq -r '.resources[].findings[] | [.severity, .rule_id, .resource, .title] | @tsv'

# only root causes (no symptoms), high and above
jq '[.resources[].findings[] | select(.is_symptom | not) | select(.severity == "HIGH" or .severity == "CRITICAL")]' rca.json

# overall severity and primary root cause
jq -r '.summary | "\(.severity): \(.primary_root_cause.title) - \(.primary_root_cause.root_cause)"' rca.json
```

> Progress messages and warnings go to **stderr**, and the report goes to **stdout**, so `-o json | jq` is safe.

---

## 9. Exit codes and CI/CD integration

| Exit code | Meaning |
|---|---|
| `0` | No finding at or above `--fail-on` (default `high`) |
| `1` | At least one finding at or above `--fail-on` |
| `2` | Error: bad arguments, resource not found, cluster unreachable, credentials rejected, missing `jq` / `kubectl` |
| `130` | Interrupted (Ctrl-C) |

### Post-deployment gate (any CI)

```bash
#!/usr/bin/env bash
APP=checkout-api NS=payments
if ! kubectl rollout status deploy/$APP -n $NS --timeout=300s; then
  ./k8s-rca.sh analyze deployment $APP -n $NS -o markdown --output-file rca-$APP.md
  cat rca-$APP.md
  exit 1
fi
# rollout succeeded - optionally fail on remaining critical issues
./k8s-rca.sh analyze deployment $APP -n $NS --fail-on critical --min-severity medium
```

### GitHub Actions

```yaml
- name: Root cause analysis on failed rollout
  if: failure()
  run: |
    ./k8s-rca-bash/k8s-rca.sh analyze deployment "$APP" -n "$NS" \
      -o markdown --output-file rca.md || true
    cat rca.md >> "$GITHUB_STEP_SUMMARY"
- uses: actions/upload-artifact@v4
  if: failure()
  with: { name: rca-report, path: rca.md }
```

### GitLab CI

```yaml
rca:
  stage: verify
  when: on_failure
  script:
    - ./k8s-rca-bash/k8s-rca.sh analyze deployment "$APP" -n "$NS" -o markdown --output-file rca.md || true
  artifacts:
    when: always
    paths: [rca.md]
```

### Jenkins (declarative)

```groovy
post {
  failure {
    sh './k8s-rca-bash/k8s-rca.sh analyze deployment ${APP} -n ${NS} -o markdown --output-file rca.md || true'
    archiveArtifacts artifacts: 'rca.md'
  }
}
```

---

## 10. Scheduling and multi-cluster usage

### Cron health check

```bash
# every 30 min: JSON report kept locally (or shipped to your own log store)
*/30 * * * * /opt/k8s-rca/k8s-rca.sh analyze cluster -o json --fail-on critical --context prod-east \
             > /var/log/k8s-rca/prod-east-$(date +\%Y\%m\%d\%H\%M).json 2>> /var/log/k8s-rca/errors.log
```

### Loop over several clusters

```bash
for ctx in prod-east prod-west staging; do
  echo "=== $ctx ==="
  ./k8s-rca.sh analyze cluster --context "$ctx" --min-severity high --no-facts \
      -o markdown --output-file "rca-$ctx.md" >/dev/null
  rc=$?
  [[ $rc -eq 1 ]] && echo "issues found in $ctx (see rca-$ctx.md)"
  [[ $rc -eq 2 ]] && echo "could not analyze $ctx"
done
```

### Every namespace with failing pods

```bash
kubectl get pods -A --no-headers | awk '$4 !~ /Running|Completed/ {print $1}' | sort -u |
while read -r ns; do
  ./k8s-rca.sh analyze namespace "$ns" -o markdown --output-file "rca-$ns.md" >/dev/null
done
```

---

## 11. Configuration file

The script sources `config/agent.conf` as bash. Values are applied in this order: built-in defaults, then the configuration file, then command-line flags.

| Setting | Default | Description |
|---|---|---|
| `LOG_TAIL` | `500` | Log lines per container |
| `REQUEST_TIMEOUT` | `30` | kubectl request timeout (seconds) |
| `COLLECT_LOGS` | `true` | Fetch container logs |
| `COLLECT_METRICS` | `true` | Use `kubectl top` |
| `RESTART_THRESHOLD` | `3` | Restarts at or above this make a pod unhealthy (triage and K8S-CRASH-002) |
| `MAX_PODS` | `25` | Pods drilled into per run in multi-resource modes |
| `MEMORY_USAGE_WARN_PCT` | `90` | Memory usage / limit threshold (K8S-RES-001) |
| `CPU_USAGE_WARN_PCT` | `90` | CPU usage / limit threshold (K8S-RES-001) |
| `QUOTA_WARN_PCT` | `90` | ResourceQuota usage threshold (K8S-RES-002) |
| `CERT_EXPIRY_WARN_DAYS` | `14` | cert-manager expiry warning window (K8S-CERT-002) |
| `MIN_CONFIDENCE` | `0` | Drop findings below this confidence |
| `MAX_EVIDENCE` | `5` | Max log lines quoted per finding |
| `REDACT_PATTERNS` | `()` | Extra regexes (ERE) to scrub from evidence |
| `DISABLED_RULES` | `()` | Rule IDs or function names to skip |
| `EXTRA_RULE_DIRS` | `()` | Extra directories containing `*.sh` rule files |
| `SEVERITY_OVERRIDES` | `()` | `"RULE-ID=LEVEL"` entries |

Example `/etc/k8s-rca/prod.conf`:

```bash
source /opt/k8s-rca/config/agent.conf            # start from the defaults
LOG_TAIL=1000
MAX_PODS=10
MIN_CONFIDENCE=60
DISABLED_RULES=(K8S-RES-001 rule_pod_net_timeout)
SEVERITY_OVERRIDES=("K8S-NODE-002=MEDIUM")
REDACT_PATTERNS=('ACCT-[0-9]{8}' 'customer_id=[0-9]+')
EXTRA_RULE_DIRS=(/opt/k8s-rca-team-rules)
```

```bash
./k8s-rca.sh analyze namespace payments --config /etc/k8s-rca/prod.conf
```

---

## 12. Permissions (RBAC)

The agent only needs **read** access. Apply the provided ClusterRole and bind it to the user or group your kubeconfig authenticates as:

```bash
# edit the subject in deploy/rbac-readonly.yaml first (Group/User/ServiceAccount name)
kubectl apply -f deploy/rbac-readonly.yaml

# verify
kubectl auth can-i list pods -A
kubectl auth can-i get pods/log -n payments
kubectl auth can-i list nodes
```

What happens when a permission is missing:

| Missing permission | Effect |
|---|---|
| `list secrets` | Missing-secret and pull-secret checks are skipped (names only would have been read) |
| `get nodes` | Node NotReady / pressure checks for the pod are skipped |
| `list pods -A` | Cluster mode cannot triage pods |
| `metrics.k8s.io` | Usage-based checks are skipped |
| `cert-manager.io` | Certificate checks are skipped |

Missing permissions never crash the run. They show up as **Collection Warnings** and as an INFO finding `K8S-RBAC-003 Analysis incomplete: agent RBAC`.

---

## 13. Security and data privacy

| Control | How |
|---|---|
| No external calls | All analysis is local Bash / `jq`. The script contains no `curl`, `wget` or HTTP calls. |
| Read-only | The `kube()` wrapper in `lib/common.sh` refuses any verb other than `get`, `logs`, `top`, `version`, `config` and `auth`. |
| Secret values never read | Secret existence is checked with `kubectl get secrets --no-headers` (server-side table output: names, types and counts only). |
| Redaction | Evidence and root causes are scrubbed of passwords, tokens, API keys, bearer/basic auth headers, JWTs, AWS access keys and `user:pass@` URL credentials, plus your `REDACT_PATTERNS`. |
| Local temporary data | Collected data goes to a `mktemp -d` directory with mode `700`. It is deleted on exit, including on Ctrl-C (unless `--keep-workdir`). |
| Existing auth | Uses your kubeconfig and context as-is (SSO / exec plugins such as `aws eks get-token`, `kubelogin`, `gke-gcloud-auth-plugin`). |

> Reports can still contain resource names, image names, IPs and log lines. Treat saved reports as **internal** data.

---

## 14. Writing your own rules

### 14.1 How discovery works

- Every `rules/*.sh` file is **sourced** at startup. Files starting with `_` are helper files and are sourced first.
- Any function named `rule_<scope>_<name>` is a rule. The scope decides when it runs:

| Prefix | Runs for | Context directory (`$CTX`) contains |
|---|---|---|
| `rule_pod_` | every analyzed pod | `pod.json events.json logs/ node.json pvc_* sa.json secrets.txt top.txt …` |
| `rule_deployment_` | every analyzed deployment | `deploy.json rs.json pods.json events.json quotas.json` |
| `rule_node_` | every analyzed node | `node.json events.json` |
| `rule_namespace_` | `analyze namespace` | `namespace.json pods.json deployments.json persistentvolumeclaims.json resourcequotas.json storageclasses.json events.json` |
| `rule_cluster_` | `analyze cluster` | `nodes.json pods.json deployments.json nodeevents.json certificates.json` |
| `rule_all_` | every scope | — |

- Register metadata so `rules list` can show the rule:
  `RULE_META[rule_pod_my_check]="CUSTOM-001|category|Human readable name"`.
  The ID is also the default ID of findings the rule emits.

### 14.2 Available variables

| Variable | Meaning |
|---|---|
| `$CTX` | Context directory of the current resource |
| `$CTX_NS`, `$CTX_NAME` | Namespace and name of the current resource |
| `$CUR_RES` | Resource key, for example `Pod payments/x` |
| `$CMD_PREFIX` | `kubectl` plus `--kubeconfig` / `--context`. Use it in validation commands. |
| `$RESTART_THRESHOLD`, `$MAX_EVIDENCE`, thresholds… | Values from the configuration file |

### 14.3 Helper functions (pod scope)

| Helper | Returns |
|---|---|
| `pj '<jq expr>'` | jq on `pod.json`, for example `pj '.spec.nodeName'` |
| `statuses_tsv` | One TSV line per container: `name restarts ready waitReason waitMsg termReason termExit lastReason lastExit finishedAt image init startedAt` (`-` = empty) |
| `cspec <container> '<jq path>'` | A field from the container spec, for example `cspec app '.resources.limits.memory'` |
| `pod_phase`, `pod_ready`, `pod_restarts` | Pod status helpers |
| `impact_sev [HIGH] [MEDIUM]` | First argument if the pod is crashing or not ready, otherwise the second |
| `events_fmt '<reason regex>' ['<msg regex>'] [container] [file]` | Formatted event lines |
| `event_count …` | Summed event count with the same filters |
| `log_hits '<ERE>' [container] [max]` | Matching log lines (previous logs first, de-duplicated) |
| `last_log_lines <container> <n>` | Last non-empty log lines |
| `c_describe`, `c_events`, `c_logs <c> [prev]` | Ready-made validation commands |
| `to_bytes`, `to_milli`, `pct` | Quantity math (`512Mi` → bytes, `250m` → millicores) |
| `lines a b c` | Joins non-empty arguments with newlines (for multi-line `emit` options) |

### 14.4 `emit` options

| Option | Required | Description |
|---|---|---|
| `--sev` | yes | `INFO`, `LOW`, `MEDIUM`, `HIGH` or `CRITICAL` |
| `--title` | yes | Short issue name |
| `--root` | yes | Root cause sentence |
| `--conf` | — | Confidence 0–100 (default 50) |
| `--evidence` | — | Newline-separated evidence lines (redacted automatically) |
| `--recs` | — | Newline-separated recommended actions |
| `--cmds` | — | Newline-separated validation commands |
| `--container` | — | Container name |
| `--symptom true` | — | Mark this finding as a consequence of another |
| `--corr KEY` | — | Correlation key, for example `secret:$CTX_NS/$name` |
| `--resource "Kind ns/name"` | — | Report against another object (for example `Node x`) |
| `--id` | — | Override the rule ID from `RULE_META` |

### 14.5 Example: flag pods using the `latest` tag

```bash
# rules/latest_tag.sh
RULE_META[rule_pod_latest_tag]="CUSTOM-002|image|Image uses latest tag"
rule_pod_latest_tag() {
  local c img
  while read -r c img; do
    [[ $img == *@* ]] && continue                       # pinned by digest
    [[ ${img##*/} == *:* && $img != *:latest ]] && continue
    emit --sev LOW --title "Image uses latest tag" --container "$c" --conf 95 \
         --root "Container '$c' uses '$img' (implicit/explicit latest): rollouts are not reproducible." \
         --evidence "Image: $img" \
         --recs "$(lines "Pin a version tag or digest." "Use imagePullPolicy: IfNotPresent with immutable tags.")" \
         --cmds "$CMD_PREFIX get pod $CTX_NAME -n $CTX_NS -o jsonpath='{.spec.containers[*].image}'"
  done < <(pj '.spec.containers[] | "\(.name) \(.image)"')
}
```

```bash
./k8s-rca.sh rules list | grep CUSTOM-002
./k8s-rca.sh analyze pod <pod> -n <ns>
```

### 14.6 Rule guidelines

- **No kubectl calls inside rules.** Read only from `$CTX`. If you need new data, add it to `collect_*` in `lib/collectors.sh`.
- Return early (`return 0`) when the rule does not apply. A failing rule never stops the run, but it should not print errors.
- Be specific in `--root`, put real names in `--cmds`, and score `--conf` honestly.
- Use `--corr` and `--symptom` so the report leads with the real cause.
- Add a scenario to `tests/fixtures/scenario.py` and a check to `tests/run_tests.sh`.

---

## 15. Offline demo and tests

`tests/fake_kubectl.py` emulates the read-only kubectl subset against a synthetic broken cluster (`tests/fixtures/scenario.py`). The scenario contains:

- an OOM crash loop
- dependency failures (connection refused, DNS)
- a missing secret
- a bad image tag
- an unschedulable pod with a missing StorageClass
- probe failures
- a MemoryPressure node and a NotReady node
- a broken CoreDNS replica
- a stuck rollout

```bash
export KUBECTL="python3 tests/fake_kubectl.py"
./k8s-rca.sh analyze pod checkout-api-768bb9ff95-abcde -n payments
./k8s-rca.sh analyze deployment checkout-api -n payments
./k8s-rca.sh analyze namespace payments
./k8s-rca.sh analyze node ip-10-0-3-30
./k8s-rca.sh analyze cluster
unset KUBECTL

tests/run_tests.sh        # 26 end-to-end checks; prints "26 passed, 0 failed"
```

---

## 16. How it works

```
k8s-rca.sh ─► collect (read-only kubectl) ─► files in temp dir ─► rules (bash + jq) ─► findings.jsonl ─► lib/report.jq ─► report + exit code
```

1. **Startup (`k8s-rca.sh`)**
   1. Parses the flags.
   2. Sources `config/agent.conf` and `lib/*.sh`.
   3. Checks that `jq` and `kubectl` are installed.
   4. Creates the private temp directory.
   5. Sources `rules/*.sh`.
2. **Collect (`lib/collectors.sh`)**
   - Every call goes through `kube()`, which enforces read-only verbs.
   - Results are saved as files: `pod.json`, `events.json`, `logs/<c>.previous`, …
   - A missing object becomes a `*.missing` marker. Permission errors go to `errors.jsonl`.
3. **Analyze (`lib/analyzers.sh`)**
   1. Writes neutral facts.
   2. Calls `run_rules <scope>`, which runs every `rule_<scope>_*` function.
   3. In multi-resource modes, ranks pods with a health score and repeats for the worst ones.
4. **Emit (`lib/engine.sh`)**: each finding is redacted and appended as one JSON line to `findings.jsonl`.
5. **Report (`lib/report.jq`)**
   1. De-duplicates findings and applies `--min-severity`.
   2. Correlates findings that share a key (the strongest stays primary, the rest become symptoms).
   3. Sorts by severity, then root cause before symptom, then confidence.
   4. Renders text, Markdown or JSON.
6. **Exit**: the worst severity is compared with `--fail-on`, and the temp directory is deleted.

Use `--keep-workdir -v` to see every rule that ran and inspect exactly what was collected:

```bash
./k8s-rca.sh analyze pod <pod> -n <ns> --keep-workdir -v
# stderr: work dir kept: /tmp/k8s-rca.AbC123
ls /tmp/k8s-rca.AbC123/ctx/pod_<ns>_<pod>/
cat /tmp/k8s-rca.AbC123/findings.jsonl | jq .
```

### Project layout

```
k8s-rca.sh            CLI: args, config, dispatch, report rendering, exit code
lib/common.sh         read-only kubectl wrapper, JSONL writers, context accessors, redaction, quantities
lib/collectors.sh     collect_pod / deployment / namespace / cluster / node into context dirs
lib/engine.sh         rule discovery, run_rules, emit, rules list
lib/analyzers.sh      orchestration per mode, fact summaries, unhealthy-pod triage
lib/report.jq         text / markdown / json rendering, de-duplication, correlation, sorting
rules/_helpers.sh     shared patterns (exit codes, DNS / refused / TLS regexes, node helpers)
rules/*.sh            diagnostic rules (drop-in plugins)
config/agent.conf     thresholds, limits, disabled rules, extra rule dirs, severity overrides
deploy/rbac-readonly.yaml  least-privilege ClusterRole + binding
tests/                fake_kubectl.py, fixtures/scenario.py, run_tests.sh
```

---

## 17. Performance tips

Each pod analysis makes about 10–15 kubectl calls and many short `jq` calls. Pods are analyzed one at a time. To go faster:

- Analyze the narrowest scope that answers your question: `pod`, then `deployment`, then `namespace`, then `cluster`.
- Lower `--max-pods` for large namespaces or clusters (for example `--max-pods 5`).
- Use `--no-metrics` when metrics-server is missing or slow (each `kubectl top` can wait for the timeout).
- Use `--no-logs` for a quick structural check. Log-based rules (DNS, refused, TLS, RBAC, crash details) are then skipped.
- Lower `--tail` (for example `--tail 200`) for chatty applications.
- Run the tool close to the API server (bastion in the same region / VPC) to reduce the latency of each call.

---

## 18. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `error: bash >= 4 required` | macOS default bash 3.2 | `brew install bash` and run with `$(brew --prefix)/bin/bash ./k8s-rca.sh …` |
| `'jq' is required but not installed` | jq missing | Install jq (section 2) |
| `$'\r': command not found` | CRLF line endings from a Windows checkout | `git config core.autocrlf input` and re-checkout, or strip `\r` with `sed` |
| `sed: -e expression … unknown option to 's'` / `grep: invalid option` | BSD tools (macOS) | Put GNU sed/grep/coreutils first on PATH |
| `error: cannot reach the Kubernetes API server` | VPN / bastion / proxy, wrong context | `kubectl get ns --context <ctx>` must work first |
| `Unauthorized` / `You must be logged in` | Expired token or SSO | Re-login (`aws sso login`, `az login`, `gcloud auth login`, `kubelogin`) |
| `error: Pod <ns>/<name> not found` (exit 2) | Wrong namespace or pod already replaced | `kubectl get pods -n <ns>`; pods in a crash loop keep the same name, so check `-n` |
| Finding `K8S-RBAC-003 Analysis incomplete` | Agent identity lacks read permission | Apply `deploy/rbac-readonly.yaml` (section 12) |
| No previous logs / "No previous log output" | Container never restarted, the log was rotated, or the process died before logging | Check the command/entrypoint; increase log retention |
| No usage lines in Findings | metrics-server not installed | Optional: install metrics-server, or use `--no-metrics` |
| Custom rule not in `rules list` | Function name doesn't start with `rule_<scope>_`, or a syntax error | `bash -n rules/my_rule.sh`; check the prefix; check `EXTRA_RULE_DIRS` paths |
| Report slow on big namespaces | Many unhealthy pods | See section 17 |
| Need to see what was collected | — | `--keep-workdir -v` (section 16) |

Run with `-v` (or `-vv`) to see every step on stderr. Use `bash -x ./k8s-rca.sh …` for a full trace.

---

## 19. Limitations

- Rules cover known failure patterns. A novel failure may only produce a generic finding, so always read the evidence.
- The analysis is a point-in-time snapshot. Kubernetes events expire (about 1 hour by default) and logs are limited to `--tail` lines.
- Deployments get the deepest drill-down. StatefulSets, DaemonSets and Jobs are analyzed at pod level.
- CPU throttling is inferred from `kubectl top` usage vs limit, not from cgroup counters.
- Pods are analyzed one at a time. The Python edition (`kubernetes-agent`) supports parallel analysis and an in-process egress block if you need more speed or stronger guarantees.

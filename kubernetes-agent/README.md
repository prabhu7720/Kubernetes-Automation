# Kubernetes Diagnostic Agent

Local, rule-based root cause analysis for Kubernetes workloads. It uses your existing kubeconfig and the `kubectl` binary. **No cluster data (logs, events, pod specs, secrets, metadata) is ever sent to an LLM or any external API.**

## Quick start

```bash
pip install pyyaml            # optional, only for YAML config; everything else is stdlib
python agent.py analyze pod checkout-api-768bb9ff95-abcde -n payments
python agent.py analyze deployment checkout-api -n payments
python agent.py analyze namespace payments
python agent.py analyze node ip-10-0-3-30.ec2.internal
python agent.py analyze cluster
python agent.py rules list

# Common flags
--kubeconfig ~/.kube/prod.yaml --context prod-east   # auth (default: kubectl's normal resolution)
-o text|markdown|json  --output-file rca.md          # output
--min-severity medium  --fail-on high                # filtering / CI exit code
--no-logs --no-metrics --tail 1000 --max-pods 50 --workers 8 -v
```

Offline demo (no cluster needed). It uses a synthetic broken cluster:

```bash
python agent.py analyze namespace payments --kubectl tests/fake_kubectl.py
python -m pytest -q tests/
```

Exit codes: `0` nothing at/above `--fail-on`, `1` findings at/above `--fail-on`, `2` usage, connection or collection error. This lets you use it as a gate in CI/CD (for example, run it after `kubectl rollout status` fails and attach the Markdown report to the pipeline).

## Data-privacy guarantees

| Control | Where |
|---|---|
| Only read-only kubectl verbs (`get`, `logs`, `top`, `version`, `auth can-i`) can be executed. Anything else raises. | `core/kube_client.py` (`_READ_ONLY_VERBS`) |
| Secret values are never fetched. Existence is checked with the server-side table printer (names, types and counts only). | `KubeClient.resource_names` |
| The Python process cannot open sockets or resolve DNS. Any accidental HTTP or SDK call fails. Only the kubectl subprocess talks to your API server. | `core/egress_guard.py` (`block_network_egress: true`) |
| Evidence is redacted (passwords, tokens, JWTs, AWS keys, `user:pass@` URLs) before it is printed. | `core/redact.py` (+ `redact_patterns`) |
| No telemetry, no third-party dependencies at runtime. | — |

## Architecture

```
agent.py (CLI)
   │
   ▼
analyzers/  ── orchestration per mode (pod / deployment / namespace / node / cluster)
   │   uses
   ├── collectors/  ── read-only kubectl calls → build Context objects (cached per run)
   ├── core/rule_engine.py ── discovers rules/*.py, evaluates applicable rules on a Context
   │        └── rules/  ── pure functions: Context → [Finding]
   └── reporting/  ── text / markdown / json rendering
```

Flow for `analyze pod X -n NS`: `PodCollector` builds a `PodContext` (pod, events, current and previous logs, owner chain, deployment, node and node allocation, PVC/PV/StorageClass, service account, secret/configmap names, metrics). Then `RuleEngine` runs every rule whose `scopes` include `pod`. `BaseAnalyzer.postprocess` dedupes, correlates, redacts and sorts the results, and `ReportGenerator` renders them.

## Module reference

### `agent.py`
CLI entry point (argparse). It parses `analyze <target>` and `rules list`, loads settings (defaults → `config/settings.yaml` → CLI flags), installs the egress guard, builds the `AnalyzerSuite`, renders the report, and maps results to exit codes. It also gives friendly errors for unreachable API servers, expired credentials and RBAC denials.

### `config/`
- **`settings.py`** – `Settings` dataclass: thresholds, collection limits, disabled rules, extra rule dirs, per-rule overrides. It loads YAML/JSON, warns on unknown keys and validates values.
- **`settings.yaml`** – documented defaults. You can point to another file with `--config` or `$K8S_AGENT_CONFIG`.

### `core/`
- **`models.py`** – `Severity` (ordered enum), `Scope`, `ResourceRef`, `Finding` (severity, evidence, root cause, confidence, recommendations, validation commands, symptom/correlation info) and `AnalysisResult` (tree of results with facts).
- **`kube_client.py`** – `KubeClient`, which wraps kubectl. It has read-only verb enforcement, `--kubeconfig/--context/--request-timeout`, JSON parsing, a thread-safe per-run cache, NotFound → `None`, and classified `KubectlError` (forbidden / unauthorized / connection / unknown resource). It also provides logs (with `--previous`), `top`, `version` and `can-i`.
- **`context.py`** – the context dataclasses handed to rules (`PodContext`, `DeploymentContext`, `NodeContext`, `NamespaceContext`, `ClusterContext`). They have helpers such as `statuses()`, `spec_of()`, `events_with_reason()`, `events_matching()`, `events_for_container()` and `search_logs()` (deduplicated regex search over previous and current logs).
- **`k8s_utils.py`** – pure helpers: `dig`, conditions, node readiness and pressure, label-selector rendering, pod triage scoring (`pod_health`), requests/limits math, event formatting.
- **`refs.py`** – extracts Secret/ConfigMap/imagePullSecret references (env, envFrom, volumes, projected), skipping optional ones.
- **`quantity.py`** – Kubernetes quantity parsing and formatting (`512Mi`, `250m`, `1e3`).
- **`redact.py`** – evidence scrubbing.
- **`egress_guard.py`** – blocks outbound sockets and DNS from the Python process.
- **`rule_engine.py`** – `RuleLoader` (plugin discovery from `rules/` and `extra_rule_dirs`, duplicate-ID protection, broken plugins isolated) and `RuleEngine` (scope filtering, per-rule exception isolation).

### `collectors/`
- **`base.py`** – `BaseCollector.safe()`. A failed step (for example, RBAC on nodes) is recorded as a collection warning instead of aborting. Connection failures abort.
- **`pod_collector.py`** – everything listed in requirement #4 for one pod. Logs are fetched only where they exist (previous logs only when the container restarted).
- **`deployment_collector.py`** – the deployment and its owned ReplicaSets/pods (filtered by owner UID, not just labels), events for the deployment and its ReplicaSets, quotas, HPA, and owner-chain resolution (Pod → ReplicaSet → Deployment/StatefulSet/DaemonSet/Job).
- **`node_collector.py`** – nodes, node events, `kubectl top nodes`, and node allocation (sum of requests/limits of non-terminated pods vs allocatable).
- **`event_collector.py`** – field-selector queries for single objects. It prefetches each namespace once in namespace or deployment mode to avoid N+1 calls.
- **`storage_collector.py`** – PVC → PV → StorageClass resolution plus PVC events, including generic ephemeral volumes.
- **`cluster_collector.py`** – namespace and cluster inventories and cert-manager Certificates (gracefully `None` if the CRD isn't installed).

### `analyzers/`
- **`base.py`** – post-processing: dedupe, `min_confidence`, **correlation** (findings with the same `correlation_key`, e.g. `secret:payments/orders-db`, keep one primary and mark the rest as symptoms), redaction, sorting (severity → root cause before symptom → confidence). Also a thread pool for parallel pod analysis.
- **`pod_analyzer.py`** – runs POD rules and builds the "Findings" fact list (phase, restarts, owner, node health, per-container state/last termination/resources/usage, PVCs, SA, events, logs collected).
- **`deployment_analyzer.py`** – DEPLOYMENT rules, then drills down into the top-N unhealthy pods (ranked by `pod_health` score).
- **`cluster_analyzer.py`** – `NamespaceAnalyzer` (groups failing pods under their Deployment), `NodeAnalyzer` and `ClusterAnalyzer` (all nodes, kube-system components, cert-manager, top-N unhealthy pods cluster-wide).

### `rules/`
| File | Rule IDs | Detects |
|---|---|---|
| `oom.py` | K8S-OOM-001 | OOMKilled / exit 137, limit vs request, live usage, JVM/Node/Go heap OOM signatures, node-level OOM |
| `crashloop.py` | K8S-CRASH-001/002/003 | CrashLoopBackOff (exit-code semantics, log signatures, arch mismatch, port in use, permission errors, short run time; marks itself a symptom of OOM, liveness or dependency failures), frequent restarts, failed Job containers |
| `imagepull.py` | K8S-IMG-001 | ImagePullBackOff / ErrImagePull / InvalidImageName / ErrImageNeverPull: tag not found, auth, rate limit, TLS, platform mismatch, disk full, network; missing imagePullSecrets |
| `probes.py` | K8S-PROBE-001/002/003 | Readiness / liveness / startup failures: HTTP 404/401/5xx, connection refused, timeouts, scheme mismatch, exec errors, undeclared probe port |
| `scheduling.py` | K8S-SCHED-001 | FailedScheduling parsed per predicate (Insufficient X, taints, affinity, topology spread, PVC binding, cordoned, max pods, hostPort, volume limits) plus autoscaler events |
| `config_errors.py` | K8S-CFG-001..004 | CreateContainerConfigError, CreateContainerError/RunContainerError, Secret missing, ConfigMap missing (proactive reference check) |
| `storage.py` | K8S-STOR-001/002 | FailedMount/FailedAttachVolume (Multi-Attach, CSI driver, NFS, perms, attach limits), PVC missing/Pending/Lost, PV missing/Failed/Released, resize pending |
| `network.py` | K8S-NET-001..004 | DNS failures (in-cluster vs external vs kube-dns unreachable), connection refused (target and well-known port, localhost sidecar case), network timeouts, CNI/IP exhaustion |
| `certificates.py` | K8S-CERT-001/002 | x509/TLS errors in logs (expired, unknown CA, SAN mismatch, mTLS) and cert-manager Certificates not ready/expiring/expired |
| `rbac.py` | K8S-RBAC-001..003 | Kubernetes RBAC forbidden (parsed user/verb/resource with a generated Role snippet), cloud IAM denials (IRSA/Workload Identity), SA token not mounted, ServiceAccount missing, agent's own missing permissions |
| `node.py` | K8S-NODE-001..003 | Node NotReady (kubelet down, runtime, PLEG, CNI, certs), Memory/Disk/PID pressure, NetworkUnavailable, evictions and preemption |
| `resources.py` | K8S-RES-001/002 | Usage near memory limit, CPU throttling, no requests/limits, node saturation, ResourceQuota/LimitRange exhaustion |
| `deployment.py` | K8S-DEPLOY-001..003 | ProgressDeadlineExceeded (with image diff vs previous revision), ReplicaFailure (PSA, admission webhooks, SA missing), unavailable replicas, paused rollout |
| `namespace.py` | K8S-NS-001/002 | Namespace stuck Terminating, Pending PVCs |
| `cluster.py` | K8S-CLUS-001 | Unhealthy kube-system components (CoreDNS escalated to Critical) |
| `_common.py` | — | shared helpers (exit-code table, fatal log patterns, command builders); not loaded as rules |

### `reporting/report_generator.py`
Renders the result tree in three formats:

- **text** – the requested layout: Resource, Severity, Primary Root Cause, Findings, then each issue with Severity, Root Cause, Evidence, Confidence, Recommended Actions and Validation Commands. Optional ANSI colour.
- **markdown** – for tickets and wikis.
- **json** – for automation.

Multi-resource runs start with a resource summary tree.

### `tests/`
`fake_kubectl.py` emulates the kubectl subset against `fixtures/scenario.py` (OOM crash loop, dependency failures, missing secret, bad image tag, unschedulable pod with a missing StorageClass, probe failures, NotReady and MemoryPressure nodes, broken CoreDNS). `test_agent.py` has unit and end-to-end tests.

## Adding a rule

Drop a file into `rules/` (or into a directory listed in `extra_rule_dirs`). No registration is needed:

```python
from core.models import Scope, Severity
from rules.base import Rule

class ExcessiveTerminationGraceRule(Rule):
    id = "CUSTOM-001"                 # unique; required for discovery
    name = "Long termination grace period"
    category = "workload"
    scopes = (Scope.POD,)             # POD, DEPLOYMENT, NODE, NAMESPACE, CLUSTER

    def evaluate(self, ctx):          # pure: read ctx, return findings, no I/O
        grace = ctx.spec.get("terminationGracePeriodSeconds", 30)
        if grace <= 300:
            return []
        return [self.finding(
            ctx, title="Long termination grace period", severity=Severity.LOW,
            root_cause=f"terminationGracePeriodSeconds={grace} slows rollouts and drains.",
            evidence=[f"terminationGracePeriodSeconds: {grace}"], confidence=90,
            recommendations=["Lower the grace period and handle SIGTERM promptly."],
            commands=[f"{ctx.cmd} get pod {ctx.name} -n {ctx.namespace} -o yaml"])]
```

Guidelines:

- Use `ctx.search_logs()` and `ctx.events_matching()` instead of re-parsing.
- Set `correlation_key` when your rule describes the same object as another rule (e.g. `secret:<ns>/<name>`).
- Set `is_symptom=True` when your finding is a consequence of something else.
- Patterns can be extended without code via `rule_overrides.<ID>.patterns.<key>`. Severity can be overridden with `rule_overrides.<ID>.severity`, and rules can be disabled with `disabled_rules`.

See `examples/custom_rules/hpa_maxed_out.py`.

## Production notes

- **Permissions**: apply `deploy/rbac-readonly.yaml` to the identity in your kubeconfig. Missing permissions are reported as an INFO finding (`K8S-RBAC-003`) instead of crashing.
- **Large clusters**: cluster mode makes about 8 list calls plus one set of calls per analyzed pod. Tune `max_pods_cluster` and `workers`. Results are cached per run.
- **metrics-server** is optional. Without it, usage-based checks are skipped.
- **Air-gapped / bastion hosts**: only Python 3.9+ and kubectl are required.
- **Scheduling**: run `analyze cluster -o json --fail-on critical` from a cron job or CI job and ship the JSON to your own log store.

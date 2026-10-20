"""Kubernetes rule pack: workload stability, scheduling, nodes, resources (events, logs and OTel metrics)."""

from __future__ import annotations

from core.models import AlertSpec, InputSpec, PanelSpec, RunbookSpec, Severity, Visualization as V
from rules.base import RulePack

_POD_RUNBOOK = RunbookSpec(
    triage=(
        "Identify affected namespace/pod and whether it belongs to a critical service.",
        "Check if a deployment or config change happened shortly before (rollout history).",
        "Determine scope: single pod, whole deployment, or node-wide.",
    ),
    investigation=(
        "uc:oomkilled", "uc:probe_failures",
        "| stats count BY {{f.namespace}} {{f.pod}} {{f.reason}} | sort - count",
    ),
    remediation=(
        "kubectl -n <namespace> describe pod <pod>   # last state, exit code, events",
        "kubectl -n <namespace> logs <pod> --previous   # logs of the crashed container",
        "kubectl -n <namespace> rollout history deploy/<name> && kubectl -n <namespace> rollout undo deploy/<name>",
        "Adjust resources.limits / liveness probe thresholds if OOM or probe related.",
    ),
    escalation="Page the owning service team if a production namespace is affected for more than 15 minutes.",
    references=("https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/",),
)

_NODE_RUNBOOK = RunbookSpec(
    triage=("Which node(s) and which condition (NotReady, DiskPressure, MemoryPressure, PIDPressure)?",
            "Are workloads being evicted or rescheduled?"),
    investigation=("uc:pod_evictions", "uc:failed_scheduling"),
    remediation=("kubectl describe node <node>   # conditions and allocated resources",
                 "kubectl cordon <node> && kubectl drain <node> --ignore-daemonsets --delete-emptydir-data",
                 "Check kubelet/containerd: journalctl -u kubelet -u containerd --since '30 min ago'",
                 "Free disk (image GC) or replace the node via the node group / cluster autoscaler."),
    escalation="Escalate to the platform team if more than one node is NotReady.",
)


class KubernetesRules(RulePack):
    domain = "kubernetes"
    title = "Kubernetes"
    description = "Pod stability, scheduling, node health and resource usage for Kubernetes clusters."
    domain_keywords = ("kubernetes", "pod", "container", "node", "namespace", "deployment", "cluster", "kubelet",
                       "eks", "aks", "gke", "helm", "workload")

    def use_cases(self):
        return [
            self.uc(
                "pod_restarts", "Pod Restart Spikes",
                description="Restart signals (BackOff, Killing, Unhealthy) per pod over time.",
                datasource="kubernetes_events",
                keywords=("pod restart", "restart spike", "container restart", "restarting pod", "pod instability"),
                filter='{{f.object_kind}}="Pod" {{f.reason}} IN ("BackOff", "Killing", "Unhealthy")',
                pipeline="| timechart span={{span}} count AS restart_signals BY {{groupby}} limit={{limit}} useother=true",
                groupby="pod", default_span="15m", visualization=V.LINE,
                single_value="| stats dc({{f.pod}}) AS restarting_pods",
                alert=AlertSpec(
                    threshold=10, metric="restart_signals", severity=Severity.HIGH, window="1h",
                    pipeline="| stats count AS restart_signals values({{f.reason}}) AS reasons latest({{f.message}}) AS last_message BY {{f.namespace}} {{f.pod}}",
                    throttle_fields=("namespace", "pod"),
                    recommended_actions=("Investigate crash loop: kubectl describe pod / kubectl logs --previous.",
                                         "Correlate with recent rollouts (kubectl rollout history).",
                                         "Verify resource limits and liveness probe configuration.")),
                related=("crashloopbackoff", "oomkilled", "top_pods_restart_count"),
                business_value="Unstable pods degrade availability long before a full outage; early detection protects SLOs.",
                runbook=_POD_RUNBOOK,
            ),
            self.uc(
                "top_pods_restart_count", "Top Pods by Restart Count",
                description="Pods with the most container restarts in the period (from k8s.container.restarts metric).",
                datasource="kubernetes_metrics", kind="raw",
                keywords=("restart count", "top pod restart", "most restart", "pod restart count", "highest restart"),
                pipeline="""
| mstats max({{m.restarts}}) AS restarts WHERE {{index}} {{extra_filter}} {{time}} span={{span}} BY {{f.namespace}} {{f.pod}}
| stats range(restarts) AS restarts_in_window max(restarts) AS total_restarts BY {{f.namespace}} {{f.pod}}
| where restarts_in_window > 0
| sort - restarts_in_window
| head {{limit}}""",
                default_span="5m", visualization=V.TABLE,
                alert=AlertSpec(threshold=5, metric="restarts_in_window", severity=Severity.HIGH, window="1h",
                                throttle_fields=("namespace", "pod")),
                related=("pod_restarts", "crashloopbackoff"), runbook=_POD_RUNBOOK,
            ),
            self.uc(
                "crashloopbackoff", "CrashLoopBackOff Pods",
                description="Pods in CrashLoopBackOff (back-off restarting failed container).",
                datasource="kubernetes_events",
                keywords=("crashloop", "container crash", "pod crash", "crashing pod", "backoff", "crashloop pod"),
                filter='({{f.reason}}="BackOff" OR "CrashLoopBackOff")',
                pipeline="""
| stats count AS backoffs latest({{f.message}}) AS last_message latest(_time) AS last_seen BY {{f.namespace}} {{f.pod}}
| sort - backoffs
| convert ctime(last_seen)""",
                single_value="| stats dc({{f.pod}}) AS crashlooping_pods",
                alert=AlertSpec(threshold=3, metric="backoffs", severity=Severity.HIGH, window="15m",
                                throttle_fields=("namespace", "pod"),
                                recommended_actions=("kubectl logs <pod> --previous to see the crash reason.",
                                                     "Roll back the last deployment if the crash started after a release.")),
                related=("pod_restarts", "oomkilled"), runbook=_POD_RUNBOOK,
            ),
            self.uc(
                "oomkilled", "OOMKilled Containers",
                description="Containers killed for exceeding memory limits and node-level OOM kills.",
                datasource="kubernetes_events",
                keywords=("oomkill", "oomkill event", "container oom", "memory kill", "oomkill container"),
                filter='("OOMKilled" OR {{f.reason}}="OOMKilling" OR {{f.reason}}="SystemOOM")',
                pipeline="""
| stats count AS oom_events latest({{f.message}}) AS last_message latest(_time) AS last_seen BY {{f.namespace}} {{f.pod}}
| sort - oom_events
| convert ctime(last_seen)""",
                single_value="| stats count AS oom_kills",
                alert=AlertSpec(threshold=0, metric="oom_events", severity=Severity.HIGH, window="15m",
                                throttle_fields=("namespace", "pod"),
                                recommended_actions=("Compare memory usage against limits for the container.",
                                                     "Raise limits or fix the leak; check for traffic spikes.")),
                related=("memory_utilization", "pod_restarts"), runbook=_POD_RUNBOOK,
            ),
            self.uc(
                "node_issues", "Node Issues",
                description="NotReady, pressure conditions, reboots and kubelet problems per node.",
                datasource="kubernetes_events",
                keywords=("node issue", "node not ready", "node pressure", "disk pressure", "memory pressure",
                          "node failure", "unhealthy node", "node problem", "node health"),
                filter='{{f.object_kind}}="Node" {{f.reason}} IN ("NodeNotReady", "NodeNotSchedulable", "NodeHasDiskPressure", "NodeHasMemoryPressure", "NodeHasPIDPressure", "EvictionThresholdMet", "Rebooted", "SystemOOM", "NodeHasInsufficientMemory", "KubeletNotReady")',
                pipeline="""
| stats count AS events values({{f.reason}}) AS conditions latest({{f.message}}) AS last_message latest(_time) AS last_seen BY {{f.object_name}}
| rename {{f.object_name}} AS node
| sort - events
| convert ctime(last_seen)""",
                alert=AlertSpec(threshold=0, metric="events", severity=Severity.HIGH, window="15m",
                                throttle_fields=("object_name",),
                                recommended_actions=("kubectl describe node <node>; check kubelet and runtime logs.",
                                                     "Cordon/drain and replace the node if it does not recover.")),
                related=("pod_evictions", "failed_scheduling"), runbook=_NODE_RUNBOOK,
            ),
            self.uc(
                "failed_scheduling", "Failed Scheduling / Pending Pods",
                description="Pods the scheduler could not place, with the reason (insufficient CPU/memory, taints, affinity).",
                datasource="kubernetes_events",
                keywords=("failedscheduling", "pending pod", "unschedulable", "insufficient cpu",
                          "insufficient memory", "scheduling failure", "cannot schedule"),
                filter='{{f.reason}}="FailedScheduling"',
                pipeline=r"""
| rex field={{f.message}} "(?<scheduling_reason>Insufficient \w+|untolerated taint|didn't match [^,.]+|volume node affinity conflict)"
| stats count AS attempts values(scheduling_reason) AS reasons latest({{f.message}}) AS last_message BY {{f.namespace}} {{f.pod}}
| sort - attempts""",
                single_value="| stats dc({{f.pod}}) AS pending_pods",
                alert=AlertSpec(threshold=5, metric="attempts", severity=Severity.MEDIUM, window="15m",
                                throttle_fields=("namespace", "pod"),
                                recommended_actions=("Check cluster capacity / autoscaler activity.",
                                                     "Review requests, nodeSelectors, taints and affinity rules.")),
                related=("node_issues",),
            ),
            self.uc(
                "container_cpu_usage", "Container CPU Usage",
                description="CPU utilisation per pod from OpenTelemetry/kubelet metrics.",
                datasource="kubernetes_metrics", kind="raw",
                keywords=("container cpu", "pod cpu", "container cpu utilization", "cpu throttling",
                          "kubernetes cpu", "pod cpu utilization"),
                pipeline="""
| mstats avg({{m.cpu}}) AS cpu WHERE {{index}} {{extra_filter}} {{time}} span={{span}} BY {{f.namespace}} {{f.pod}}
| timechart span={{span}} max(cpu) AS cpu BY {{f.pod}} limit={{limit}} useother=true""",
                default_span="5m", visualization=V.LINE,
                alert=AlertSpec(threshold=90, metric="avg_cpu", severity=Severity.MEDIUM, window="15m",
                                pipeline="| mstats avg({{m.cpu}}) AS avg_cpu WHERE {{index}} {{extra_filter}} BY {{f.namespace}} {{f.pod}}",
                                throttle_fields=("namespace", "pod"),
                                recommended_actions=("Check for CPU throttling against limits.",
                                                     "Scale out (HPA) or raise CPU requests/limits.")),
                related=("memory_utilization",),
            ),
            self.uc(
                "memory_utilization", "Pod Memory Utilization",
                description="Memory working set as a percentage of the container limit, per pod.",
                datasource="kubernetes_metrics", kind="raw",
                keywords=("pod memory", "container memory", "memory limit", "kubernetes memory",
                          "pod memory utilization", "container memory utilization"),
                pipeline="""
| mstats avg({{m.memory}}) AS mem_bytes max({{m.memory_limit}}) AS mem_limit WHERE {{index}} {{extra_filter}} {{time}} span={{span}} BY {{f.namespace}} {{f.pod}}
| eval mem_pct=if(mem_limit > 0, round(mem_bytes / mem_limit * 100, 2), null())
| timechart span={{span}} max(mem_pct) AS mem_pct BY {{f.pod}} limit={{limit}} useother=true""",
                default_span="5m", visualization=V.LINE,
                alert=AlertSpec(threshold=90, metric="mem_pct", severity=Severity.HIGH, window="15m",
                                pipeline="""
| mstats avg({{m.memory}}) AS mem_bytes max({{m.memory_limit}}) AS mem_limit WHERE {{index}} {{extra_filter}} BY {{f.namespace}} {{f.pod}}
| eval mem_pct=round(mem_bytes / mem_limit * 100, 2)""",
                                throttle_fields=("namespace", "pod"),
                                recommended_actions=("Pods above 90% of limit are at imminent OOM risk.",
                                                     "Raise limits or investigate memory leaks.")),
                related=("oomkilled",),
            ),
            self.uc(
                "deployment_failures", "Deployment Failures",
                description="Failed rollouts and controller errors for Deployments/ReplicaSets/StatefulSets/DaemonSets.",
                datasource="kubernetes_events",
                keywords=("deployment failure", "failed deployment", "deployment fail", "deployment error",
                          "replicaset error", "progress deadline", "rollout stuck"),
                filter='{{f.object_kind}} IN ("Deployment", "ReplicaSet", "StatefulSet", "DaemonSet") {{f.reason}} IN ("FailedCreate", "ProgressDeadlineExceeded", "FailedDelete", "ReplicaSetCreateError", "FailedUpdate")',
                pipeline="""
| stats count AS failures values({{f.reason}}) AS reasons latest({{f.message}}) AS last_message latest(_time) AS last_seen BY {{f.namespace}} {{f.object_kind}} {{f.object_name}}
| sort - failures
| convert ctime(last_seen)""",
                alert=AlertSpec(threshold=0, metric="failures", severity=Severity.HIGH, window="15m",
                                throttle_fields=("namespace", "object_name"),
                                recommended_actions=("kubectl rollout status deploy/<name> -n <ns>",
                                                     "Check quota/admission webhook errors in the message.",
                                                     "Roll back with kubectl rollout undo if needed.")),
                related=("image_pull_errors", "crashloopbackoff"),
            ),
            self.uc(
                "image_pull_errors", "Image Pull Errors",
                description="ErrImagePull / ImagePullBackOff by pod and image.",
                datasource="kubernetes_events",
                keywords=("imagepull", "imagepull error", "pull error", "registry error", "image pull fail"),
                filter='{{f.reason}} IN ("Failed", "ErrImagePull", "ImagePullBackOff", "BackOff") ("Failed to pull image" OR "ImagePullBackOff" OR "ErrImagePull" OR "Back-off pulling image")',
                pipeline=r"""
| rex field={{f.message}} "image \W?(?<image>[\w.\-/:@]+)"
| stats count AS failures latest({{f.message}}) AS last_message BY {{f.namespace}} {{f.pod}} image
| sort - failures""",
                alert=AlertSpec(threshold=0, metric="failures", severity=Severity.MEDIUM, window="15m"),
                related=("deployment_failures",),
            ),
            self.uc(
                "probe_failures", "Liveness / Readiness Probe Failures",
                description="Failing health probes per pod and probe type.",
                datasource="kubernetes_events",
                keywords=("probe failure", "liveness probe", "readiness probe", "health check fail", "unhealthy pod"),
                filter='{{f.reason}}="Unhealthy"',
                pipeline="""
| eval probe=case(like({{q.message}}, "Liveness%"), "liveness", like({{q.message}}, "Readiness%"), "readiness", like({{q.message}}, "Startup%"), "startup", true(), "other")
| stats count AS failures BY {{f.namespace}} {{f.pod}} probe
| sort - failures
| head {{limit}}""",
                alert=AlertSpec(threshold=20, metric="failures", severity=Severity.MEDIUM, window="15m"),
            ),
            self.uc(
                "pod_evictions", "Pod Evictions",
                description="Pods evicted due to node resource pressure.",
                datasource="kubernetes_events",
                keywords=("eviction", "pod eviction", "evicted pod"),
                filter='{{f.reason}}="Evicted"',
                pipeline="""
| stats count AS evictions latest({{f.message}}) AS last_message BY {{f.namespace}} {{f.pod}}
| sort - evictions""",
                alert=AlertSpec(threshold=5, metric="evictions", severity=Severity.MEDIUM, window="1h"),
                related=("node_issues",), runbook=_NODE_RUNBOOK,
            ),
            self.uc(
                "namespace_health", "Namespace Health (Warning Events)",
                description="Warning events per namespace with affected objects and reasons.",
                datasource="kubernetes_events",
                keywords=("namespace health", "warning event", "namespace warning", "kubernetes warning",
                          "cluster event", "namespace issue"),
                filter='{{f.type}}="Warning"',
                pipeline="""
| stats count AS warnings dc({{f.object_name}}) AS affected_objects values({{f.reason}}) AS reasons BY {{f.namespace}}
| sort - warnings""",
                single_value="| stats count AS warnings",
                alert=AlertSpec(threshold=200, metric="warnings", severity=Severity.MEDIUM, window="1h",
                                throttle_fields=("namespace",)),
            ),
            self.uc(
                "k8s_warning_trend", "Kubernetes Warning Event Trend",
                description="Warning events over time per namespace.",
                datasource="kubernetes_events",
                keywords=("warning trend", "kubernetes event trend", "event trend", "warning event trend"),
                filter='{{f.type}}="Warning"',
                pipeline="| timechart span={{span}} count BY {{f.namespace}} limit={{limit}} useother=true",
                visualization=V.LINE, default_span="15m",
            ),
            self.uc(
                "container_log_errors", "Container Log Errors",
                description="Error/exception lines in container logs by namespace and container.",
                datasource="kubernetes_logs",
                keywords=("container error", "pod error", "container log error", "pod log error"),
                filter='(ERROR OR Exception OR FATAL OR panic)',
                pipeline="""
| stats count AS errors BY {{f.namespace}} {{f.container}}
| sort - errors
| head {{limit}}""",
                visualization=V.COLUMN,
                alert=AlertSpec(threshold=500, metric="errors", severity=Severity.MEDIUM, window="15m"),
            ),
        ]

    def dashboards(self):
        return [
            self.bp(
                "kubernetes_health", "Kubernetes Cluster Health",
                description="Workload stability, scheduling, node conditions and resource usage.",
                keywords=("kubernetes health", "kubernetes", "cluster health", "kubernetes cluster",
                          "kubernetes overview", "pod health", "kubernetes monitoring"),
                inputs=(InputSpec("namespace", "Namespace", "namespace"),),
                panels=(
                    PanelSpec("namespace_health", "Warning Events", V.SINGLE),
                    PanelSpec("crashloopbackoff", "CrashLooping Pods", V.SINGLE),
                    PanelSpec("oomkilled", "OOMKilled Events", V.SINGLE),
                    PanelSpec("failed_scheduling", "Unschedulable Pods", V.SINGLE),
                    PanelSpec("k8s_warning_trend", "Warning Events by Namespace"),
                    PanelSpec("pod_restarts", "Restart Signals by Pod"),
                    PanelSpec("container_cpu_usage", "CPU by Pod"),
                    PanelSpec("memory_utilization", "Memory % of Limit by Pod"),
                    PanelSpec("crashloopbackoff", "CrashLoopBackOff Details"),
                    PanelSpec("top_pods_restart_count", "Top Pods by Restarts"),
                    PanelSpec("node_issues", "Node Conditions"),
                    PanelSpec("deployment_failures", "Deployment Failures"),
                    PanelSpec("failed_scheduling", "Scheduling Failures"),
                ),
            ),
        ]

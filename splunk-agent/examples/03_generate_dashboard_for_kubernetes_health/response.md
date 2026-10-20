# Kubernetes Cluster Health

- **Request:** Generate dashboard for Kubernetes health
- **Artifact:** dashboard  |  **Matched:** namespace_health, crashloopbackoff, oomkilled, failed_scheduling, k8s_warning_trend, pod_restarts, container_cpu_usage, memory_utilization, top_pods_restart_count, node_issues, deployment_failures  |  **Confidence:** 100%

## 1. Generated SPL

Ad-hoc (inline time range):

```spl
index=k8s_events sourcetype="kube:object:events" earliest=-24h latest=now object.type="Warning"
| timechart span=15m count BY object.involvedObject.namespace limit=10 useother=true
```

Saved-search form (time range set by schedule/dispatch):

```spl
index=k8s_events sourcetype="kube:object:events" object.type="Warning"
| timechart span=15m count BY object.involvedObject.namespace limit=10 useother=true
```

_13 panel searches are included in the dashboard definition and JSON output._

## 2. Explanation

- Dashboard blueprint 'kubernetes_health' selected with 13 panels; panels share a global time picker.
- Use case 'Kubernetes Warning Event Trend': Warning events over time per namespace.
- Datasource 'kubernetes_events' resolved to index=k8s_events sourcetype="kube:object:events" (selected from the discovered catalog, confidence 100%). Field mapping: namespace->object.involvedObject.namespace, type->object.type.
- Retrieves events from index k8s_events (sourcetype kube:object:events) for -24h to now matching: object.type="Warning".
- `timechart` buckets results over time (span 15m) computing count, one series per object.involvedObject.namespace.

## 3. Visualization Recommendation

- **Primary:** line (`splunk.line`)
- **Why:** Time-bucketed series are best read as a trend line.
- **Alternatives:** area, column

## 4. Dashboard Component Suggestions

| Panel | Kind | Studio type | Use case |
|---|---|---|---|
| Warning Events | kpi | `splunk.singlevalue` | namespace_health |
| CrashLooping Pods | kpi | `splunk.singlevalue` | crashloopbackoff |
| OOMKilled Events | kpi | `splunk.singlevalue` | oomkilled |
| Unschedulable Pods | kpi | `splunk.singlevalue` | failed_scheduling |
| Warning Events by Namespace | chart | `splunk.line` | k8s_warning_trend |
| Restart Signals by Pod | chart | `splunk.line` | pod_restarts |
| CPU by Pod | chart | `splunk.line` | container_cpu_usage |
| Memory % of Limit by Pod | chart | `splunk.line` | memory_utilization |
| CrashLoopBackOff Details | table | `splunk.table` | crashloopbackoff |
| Top Pods by Restarts | table | `splunk.table` | top_pods_restart_count |
| Node Conditions | table | `splunk.table` | node_issues |
| Deployment Failures | table | `splunk.table` | deployment_failures |
| Scheduling Failures | table | `splunk.table` | failed_scheduling |

## 5. Alert Recommendations

**Alert:** Namespace Health (Warning Events)
- Severity: **Medium** (alert.severity=4)
- Threshold: `warnings > 200` evaluated over 1h
- Schedule: `0 * * * *` (hourly at :00), window `-1h@h` to `@h`
- Throttle: object.involvedObject.namespace for 1h
- Recommended actions:
  - Review the matching results and confirm the condition is genuine.
  - Identify the owning team / asset and notify them.
  - Document findings and tune the threshold if this is noise.

```spl
index=k8s_events sourcetype="kube:object:events" object.type="Warning"
| stats count AS warnings dc(object.involvedObject.name) AS affected_objects values(object.reason) AS reasons BY object.involvedObject.namespace
| sort - warnings
| where warnings > 200
```

**Alert:** CrashLoopBackOff Pods
- Severity: **High** (alert.severity=5)
- Threshold: `backoffs > 3` evaluated over 15m
- Schedule: `*/15 * * * *` (every 15 minutes), window `-15m@m` to `@m`
- Throttle: object.involvedObject.namespace, object.involvedObject.name for 1h
- Recommended actions:
  - kubectl logs <pod> --previous to see the crash reason.
  - Roll back the last deployment if the crash started after a release.

```spl
index=k8s_events sourcetype="kube:object:events" (object.reason="BackOff" OR "CrashLoopBackOff")
| stats count AS backoffs latest(object.message) AS last_message latest(_time) AS last_seen BY object.involvedObject.namespace object.involvedObject.name
| sort - backoffs
| convert ctime(last_seen)
| where backoffs > 3
```

**Alert:** OOMKilled Containers
- Severity: **High** (alert.severity=5)
- Threshold: `oom_events > 0` evaluated over 15m
- Schedule: `*/15 * * * *` (every 15 minutes), window `-15m@m` to `@m`
- Throttle: object.involvedObject.namespace, object.involvedObject.name for 1h
- Recommended actions:
  - Compare memory usage against limits for the container.
  - Raise limits or fix the leak; check for traffic spikes.

```spl
index=k8s_events sourcetype="kube:object:events" ("OOMKilled" OR object.reason="OOMKilling" OR object.reason="SystemOOM")
| stats count AS oom_events latest(object.message) AS last_message latest(_time) AS last_seen BY object.involvedObject.namespace object.involvedObject.name
| sort - oom_events
| convert ctime(last_seen)
| where oom_events > 0
```

**Alert:** Failed Scheduling / Pending Pods
- Severity: **Medium** (alert.severity=4)
- Threshold: `attempts > 5` evaluated over 15m
- Schedule: `*/15 * * * *` (every 15 minutes), window `-15m@m` to `@m`
- Throttle: object.involvedObject.namespace, object.involvedObject.name for 1h
- Recommended actions:
  - Check cluster capacity / autoscaler activity.
  - Review requests, nodeSelectors, taints and affinity rules.

```spl
index=k8s_events sourcetype="kube:object:events" object.reason="FailedScheduling"
| rex field=object.message "(?<scheduling_reason>Insufficient \w+|untolerated taint|didn't match [^,.]+|volume node affinity conflict)"
| stats count AS attempts values(scheduling_reason) AS reasons latest(object.message) AS last_message BY object.involvedObject.namespace object.involvedObject.name
| sort - attempts
| where attempts > 5
```

**Alert:** Pod Restart Spikes
- Severity: **High** (alert.severity=5)
- Threshold: `restart_signals > 10` evaluated over 1h
- Schedule: `0 * * * *` (hourly at :00), window `-1h@h` to `@h`
- Throttle: object.involvedObject.namespace, object.involvedObject.name for 1h
- Recommended actions:
  - Investigate crash loop: kubectl describe pod / kubectl logs --previous.
  - Correlate with recent rollouts (kubectl rollout history).
  - Verify resource limits and liveness probe configuration.

```spl
index=k8s_events sourcetype="kube:object:events" object.involvedObject.kind="Pod" object.reason IN ("BackOff", "Killing", "Unhealthy")
| stats count AS restart_signals values(object.reason) AS reasons latest(object.message) AS last_message BY object.involvedObject.namespace object.involvedObject.name
| where restart_signals > 10
```

savedsearches.conf:

```ini
[AUTO - Alert - Namespace Health (Warning Events)]
action.email.inline = 1
action.email.message.alert = Splunk alert "Namespace Health (Warning Events)" fired. \
 \
Condition : warnings > 200 \
Severity  : medium \
Summary   : Warning events per namespace with affected objects and reasons. \
 \
Recommended actions: \
- Review the matching results and confirm the condition is genuine. \
- Identify the owning team / asset and notify them. \
- Document findings and tune the threshold if this is noise. \
 \
Results: $results.link$
action.email.sendresults = 1
action.email.subject = [MEDIUM] $name$
action.email.to = ${SPLUNK_AGENT_ALERT_EMAIL:-}
action.webhook.param.url = ${SPLUNK_AGENT_ALERT_WEBHOOK:-}
actions = email,webhook
alert.digest_mode = 1
alert.severity = 4
alert.suppress = 1
alert.suppress.fields = object.involvedObject.namespace
alert.suppress.period = 1h
alert.track = 1
alert_comparator = greater than
alert_threshold = 0
alert_type = number of events
cron_schedule = 0 * * * *
description = Warning events per namespace with affected objects and reasons.
dispatch.earliest_time = -1h@h
dispatch.latest_time = @h
is_scheduled = 1
schedule_window = auto
search = index=k8s_events sourcetype="kube:object:events" object.type="Warning" \
| stats count AS warnings dc(object.involvedObject.name) AS affected_objects values(object.reason) AS reasons BY object.involvedObject.namespace \
| sort - warnings \
| where warnings > 200

[AUTO - Alert - CrashLoopBackOff Pods]
action.email.inline = 1
action.email.message.alert = Splunk alert "CrashLoopBackOff Pods" fired. \
 \
Condition : backoffs > 3 \
Severity  : high \
Summary   : Pods in CrashLoopBackOff (back-off restarting failed container). \
 \
Recommended actions: \
- kubectl logs <pod> --previous to see the crash reason. \
- Roll back the last deployment if the crash started after a release. \
 \
Results: $results.link$
action.email.sendresults = 1
action.email.subject = [HIGH] $name$
action.email.to = ${SPLUNK_AGENT_ALERT_EMAIL:-}
action.webhook.param.url = ${SPLUNK_AGENT_ALERT_WEBHOOK:-}
actions = email,webhook
alert.digest_mode = 1
alert.severity = 5
alert.suppress = 1
alert.suppress.fields = object.involvedObject.namespace,object.involvedObject.name
alert.suppress.period = 1h
alert.track = 1
alert_comparator = greater than
alert_threshold = 0
alert_type = number of events
cron_schedule = */15 * * * *
description = Pods in CrashLoopBackOff (back-off restarting failed container).
dispatch.earliest_time = -15m@m
dispatch.latest_time = @m
is_scheduled = 1
schedule_window = auto
search = index=k8s_events sourcetype="kube:object:events" (object.reason="BackOff" OR "CrashLoopBackOff") \
| stats count AS backoffs latest(object.message) AS last_message latest(_time) AS last_seen BY object.involvedObject.namespace object.involvedObject.name \
| sort - backoffs \
| convert ctime(last_seen) \
| where backoffs > 3

[AUTO - Alert - OOMKilled Containers]
action.email.inline = 1
action.email.message.alert = Splunk alert "OOMKilled Containers" fired. \
 \
Condition : oom_events > 0 \
Severity  : high \
Summary   : Containers killed for exceeding memory limits and node-level OOM kills. \
 \
Recommended actions: \
- Compare memory usage against limits for the container. \
- Raise limits or fix the leak; check for traffic spikes. \
 \
Results: $results.link$
action.email.sendresults = 1
action.email.subject = [HIGH] $name$
action.email.to = ${SPLUNK_AGENT_ALERT_EMAIL:-}
action.webhook.param.url = ${SPLUNK_AGENT_ALERT_WEBHOOK:-}
actions = email,webhook
alert.digest_mode = 1
alert.severity = 5
alert.suppress = 1
alert.suppress.fields = object.involvedObject.namespace,object.involvedObject.name
alert.suppress.period = 1h
alert.track = 1
alert_comparator = greater than
alert_threshold = 0
alert_type = number of events
cron_schedule = */15 * * * *
description = Containers killed for exceeding memory limits and node-level OOM kills.
dispatch.earliest_time = -15m@m
dispatch.latest_time = @m
is_scheduled = 1
schedule_window = auto
search = index=k8s_events sourcetype="kube:object:events" ("OOMKilled" OR object.reason="OOMKilling" OR object.reason="SystemOOM") \
| stats count AS oom_events latest(object.message) AS last_message latest(_time) AS last_seen BY object.involvedObject.namespace object.involvedObject.name \
| sort - oom_events \
| convert ctime(last_seen) \
| where oom_events > 0

[AUTO - Alert - Failed Scheduling / Pending Pods]
action.email.inline = 1
action.email.message.alert = Splunk alert "Failed Scheduling / Pending Pods" fired. \
 \
Condition : attempts > 5 \
Severity  : medium \
Summary   : Pods the scheduler could not place, with the reason (insufficient CPU/memory, taints, affinity). \
 \
Recommended actions: \
- Check cluster capacity / autoscaler activity. \
- Review requests, nodeSelectors, taints and affinity rules. \
 \
Results: $results.link$
action.email.sendresults = 1
action.email.subject = [MEDIUM] $name$
action.email.to = ${SPLUNK_AGENT_ALERT_EMAIL:-}
action.webhook.param.url = ${SPLUNK_AGENT_ALERT_WEBHOOK:-}
actions = email,webhook
alert.digest_mode = 1
alert.severity = 4
alert.suppress = 1
alert.suppress.fields = object.involvedObject.namespace,object.involvedObject.name
alert.suppress.period = 1h
alert.track = 1
alert_comparator = greater than
alert_threshold = 0
alert_type = number of events
cron_schedule = */15 * * * *
description = Pods the scheduler could not place, with the reason (insufficient CPU/memory, taints, affinity).
dispatch.earliest_time = -15m@m
dispatch.latest_time = @m
is_scheduled = 1
schedule_window = auto
search = index=k8s_events sourcetype="kube:object:events" object.reason="FailedScheduling" \
| rex field=object.message "(?<scheduling_reason>Insufficient \w+|untolerated taint|didn't match [^,.]+|volume node affinity conflict)" \
| stats count AS attempts values(scheduling_reason) AS reasons latest(object.message) AS last_message BY object.involvedObject.namespace object.involvedObject.name \
| sort - attempts \
| where attempts > 5

[AUTO - Alert - Pod Restart Spikes]
action.email.inline = 1
action.email.message.alert = Splunk alert "Pod Restart Spikes" fired. \
 \
Condition : restart_signals > 10 \
Severity  : high \
Summary   : Restart signals (BackOff, Killing, Unhealthy) per pod over time. \
 \
Recommended actions: \
- Investigate crash loop: kubectl describe pod / kubectl logs --previous. \
- Correlate with recent rollouts (kubectl rollout history). \
- Verify resource limits and liveness probe configuration. \
 \
Results: $results.link$
action.email.sendresults = 1
action.email.subject = [HIGH] $name$
action.email.to = ${SPLUNK_AGENT_ALERT_EMAIL:-}
action.webhook.param.url = ${SPLUNK_AGENT_ALERT_WEBHOOK:-}
actions = email,webhook
alert.digest_mode = 1
alert.severity = 5
alert.suppress = 1
alert.suppress.fields = object.involvedObject.namespace,object.involvedObject.name
alert.suppress.period = 1h
alert.track = 1
alert_comparator = greater than
alert_threshold = 0
alert_type = number of events
cron_schedule = 0 * * * *
description = Restart signals (BackOff, Killing, Unhealthy) per pod over time.
dispatch.earliest_time = -1h@h
dispatch.latest_time = @h
is_scheduled = 1
schedule_window = auto
search = index=k8s_events sourcetype="kube:object:events" object.involvedObject.kind="Pod" object.reason IN ("BackOff", "Killing", "Unhealthy") \
| stats count AS restart_signals values(object.reason) AS reasons latest(object.message) AS last_message BY object.involvedObject.namespace object.involvedObject.name \
| where restart_signals > 10
```

## 6. Report Definition

**Report:** Kubernetes Warning Event Trend
**Description:** Kubernetes Warning Event Trend tracks platform reliability so SRE teams can act before users are affected: Warning events over time per namespace.
**Schedule:** `0 6 * * *` (daily at 06:00)
**Time range:** `-24h` to `now`
**Visualization:** line

```spl
index=k8s_events sourcetype="kube:object:events" object.type="Warning"
| timechart span=15m count BY object.involvedObject.namespace limit=10 useother=true
```

savedsearches.conf:

```ini
[AUTO - Report - Kubernetes Warning Event Trend]
cron_schedule = 0 6 * * *
description = Warning events over time per namespace.
dispatch.earliest_time = -24h
dispatch.latest_time = now
display.general.type = visualizations
display.page.search.tab = visualizations
display.visualizations.charting.chart = line
display.visualizations.type = charting
is_scheduled = 1
request.ui_dispatch_app = search
request.ui_dispatch_view = search
schedule_window = auto
search = index=k8s_events sourcetype="kube:object:events" object.type="Warning" \
| timechart span=15m count BY object.involvedObject.namespace limit=10 useother=true
```

## Dashboard

**Dashboard Studio:** Kubernetes Cluster Health (`auto_kubernetes_cluster_health`), 13 panels, global time picker + drilldowns.

| Panel | Kind | Type | Use case |
|---|---|---|---|
| Warning Events | kpi | `splunk.singlevalue` | namespace_health |
| CrashLooping Pods | kpi | `splunk.singlevalue` | crashloopbackoff |
| OOMKilled Events | kpi | `splunk.singlevalue` | oomkilled |
| Unschedulable Pods | kpi | `splunk.singlevalue` | failed_scheduling |
| Warning Events by Namespace | chart | `splunk.line` | k8s_warning_trend |
| Restart Signals by Pod | chart | `splunk.line` | pod_restarts |
| CPU by Pod | chart | `splunk.line` | container_cpu_usage |
| Memory % of Limit by Pod | chart | `splunk.line` | memory_utilization |
| CrashLoopBackOff Details | table | `splunk.table` | crashloopbackoff |
| Top Pods by Restarts | table | `splunk.table` | top_pods_restart_count |
| Node Conditions | table | `splunk.table` | node_issues |
| Deployment Failures | table | `splunk.table` | deployment_failures |
| Scheduling Failures | table | `splunk.table` | failed_scheduling |

Full definition written to `dashboard_<name>.json` (Studio source) and `.xml` (deployable view).

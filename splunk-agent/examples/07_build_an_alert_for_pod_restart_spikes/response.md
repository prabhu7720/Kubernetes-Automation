# Pod Restart Spikes

- **Request:** Build an alert for pod restart spikes
- **Artifact:** alert  |  **Matched:** pod_restarts  |  **Confidence:** 100%
- **Other candidates:** top_pods_restart_count

## 1. Generated SPL

Ad-hoc (inline time range):

```spl
index=k8s_events sourcetype="kube:object:events" earliest=-24h latest=now object.involvedObject.kind="Pod" object.reason IN ("BackOff", "Killing", "Unhealthy")
| timechart span=15m count AS restart_signals BY object.involvedObject.name limit=10 useother=true
```

Saved-search form (time range set by schedule/dispatch):

```spl
index=k8s_events sourcetype="kube:object:events" object.involvedObject.kind="Pod" object.reason IN ("BackOff", "Killing", "Unhealthy")
| timechart span=15m count AS restart_signals BY object.involvedObject.name limit=10 useother=true
```

## 2. Explanation

- Use case 'Pod Restart Spikes': Restart signals (BackOff, Killing, Unhealthy) per pod over time.
- Datasource 'kubernetes_events' resolved to index=k8s_events sourcetype="kube:object:events" (selected from the discovered catalog, confidence 100%). Field mapping: message->object.message, namespace->object.involvedObject.namespace, object_kind->object.involvedObject.kind, pod->object.involvedObject.name, reason->object.reason.
- Retrieves events from index k8s_events (sourcetype kube:object:events) for -24h to now matching: object.involvedObject.kind="Pod" object.reason IN ("BackOff", "Killing", "Unhealthy").
- `timechart` buckets results over time (span 15m) computing count, one series per object.involvedObject.name.

## 3. Visualization Recommendation

- **Primary:** line (`splunk.line`)
- **Why:** Time-bucketed series are best read as a trend line.
- **Alternatives:** area, column

## 4. Dashboard Component Suggestions

| Panel | Kind | Studio type | Use case |
|---|---|---|---|
| Pod Restart Spikes (total) | kpi | `splunk.singlevalue` | pod_restarts |
| Pod Restart Spikes | chart | `splunk.line` | pod_restarts |
| CrashLoopBackOff Pods | table | `splunk.table` | crashloopbackoff |
| OOMKilled Containers | table | `splunk.table` | oomkilled |
| Top Pods by Restart Count | table | `splunk.table` | top_pods_restart_count |

## 5. Alert Recommendations

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

**Report:** Pod Restart Spikes
**Description:** Unstable pods degrade availability long before a full outage; early detection protects SLOs.
**Schedule:** `0 6 * * *` (daily at 06:00)
**Time range:** `-24h` to `now`
**Visualization:** line

```spl
index=k8s_events sourcetype="kube:object:events" object.involvedObject.kind="Pod" object.reason IN ("BackOff", "Killing", "Unhealthy")
| timechart span=15m count AS restart_signals BY object.involvedObject.name limit=10 useother=true
```

savedsearches.conf:

```ini
[AUTO - Report - Pod Restart Spikes]
cron_schedule = 0 6 * * *
description = Restart signals (BackOff, Killing, Unhealthy) per pod over time.
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
search = index=k8s_events sourcetype="kube:object:events" object.involvedObject.kind="Pod" object.reason IN ("BackOff", "Killing", "Unhealthy") \
| timechart span=15m count AS restart_signals BY object.involvedObject.name limit=10 useother=true
```

## Runbook

Runbook written to `runbook_pod_restart_spikes_runbook.md`.

# Pod Restart Spikes Runbook

| Field | Value |
|---|---|
| Domain | kubernetes |
| Severity | High |
| Trigger | `restart_signals > 10` over 1h |
| Schedule | 0 * * * * (hourly at :00) |
| MITRE ATT&CK | n/a |

## 1. Purpose
Restart signals (BackOff, Killing, Unhealthy) per pod over time.

**Business impact:** Unstable pods degrade availability long before a full outage; early detection protects SLOs.

## 2. Detection logic
```spl
index=k8s_events sourcetype="kube:object:events" object.involvedObject.kind="Pod" object.reason IN ("BackOff", "Killing", "Unhealthy")
| stats count AS restart_signals values(object.reason) AS reasons latest(object.message) AS last_message BY object.involvedObject.namespace object.involvedObject.name
| where restart_signals > 10
```

## 3. Triage (first 15 minutes)
1. Identify affected namespace/pod and whether it belongs to a critical service.
2. Check if a deployment or config change happened shortly before (rollout history).
3. Determine scope: single pod, whole deployment, or node-wide.

## 4. Investigation searches
**OOMKilled Containers**

```spl
index=k8s_events sourcetype="kube:object:events" earliest=-24h latest=now ("OOMKilled" OR object.reason="OOMKilling" OR object.reason="SystemOOM")
| stats count AS oom_events latest(object.message) AS last_message latest(_time) AS last_seen BY object.involvedObject.namespace object.involvedObject.name
| sort - oom_events
| convert ctime(last_seen)
```

**Liveness / Readiness Probe Failures**

```spl
index=k8s_events sourcetype="kube:object:events" earliest=-24h latest=now object.reason="Unhealthy"
| eval probe=case(like('object.message', "Liveness%"), "liveness", like('object.message', "Readiness%"), "readiness", like('object.message', "Startup%"), "startup", true(), "other")
| stats count AS failures BY object.involvedObject.namespace object.involvedObject.name probe
| sort - failures
| head 10
```

```spl
index=k8s_events sourcetype="kube:object:events" earliest=-24h latest=now object.involvedObject.kind="Pod" object.reason IN ("BackOff", "Killing", "Unhealthy")
| stats count BY object.involvedObject.namespace object.involvedObject.name object.reason | sort - count
```

## 5. Remediation
1. kubectl -n <namespace> describe pod <pod>   # last state, exit code, events
2. kubectl -n <namespace> logs <pod> --previous   # logs of the crashed container
3. kubectl -n <namespace> rollout history deploy/<name> && kubectl -n <namespace> rollout undo deploy/<name>
4. Adjust resources.limits / liveness probe thresholds if OOM or probe related.

### Alert-specific actions
- Investigate crash loop: kubectl describe pod / kubectl logs --previous.
- Correlate with recent rollouts (kubectl rollout history).
- Verify resource limits and liveness probe configuration.

## 6. Escalation
Page the owning service team if a production namespace is affected for more than 15 minutes.

## 7. References
- https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/

## 8. Post-incident
- Record root cause and timeline in the incident ticket.
- Tune the threshold / add suppressions if the alert was noisy.
- Update this runbook with anything that would have helped.


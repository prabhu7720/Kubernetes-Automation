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

# HTTP Error Responses Runbook

| Field | Value |
|---|---|
| Domain | application |
| Severity | High |
| Trigger | `errors > 100` over 1h |
| Schedule | 0 * * * * (hourly at :00) |
| MITRE ATT&CK | n/a |

## 1. Purpose
HTTP responses matching the selected status codes (default 5xx) over time.

**Business impact:** Server-side errors directly impact customers and revenue; tracking them protects SLAs.

## 2. Detection logic
```spl
index=web sourcetype=access_combined status IN (500)
| stats count AS errors dc(host) AS affected_hosts dc(uri) AS affected_endpoints
| where errors > 100
```

## 3. Triage (first 15 minutes)
1. Which hosts/endpoints are returning errors and since when?
2. Did a deployment, config change or dependency incident coincide with the spike?

## 4. Investigation searches
**Slowest Endpoints**

```spl
index=web sourcetype=access_combined earliest=-24h latest=now request_time=*
| stats count AS requests avg(request_time) AS avg_ms perc95(request_time) AS p95_ms BY uri
| where requests >= 10
| eval avg_ms=round(avg_ms, 2), p95_ms=round(p95_ms, 2)
| sort - p95_ms
| head 10
```

**Top Application Exceptions**

```spl
index=app_logs sourcetype=_json earliest=-24h latest=now (Exception OR Traceback OR "stack trace")
| rex field=_raw "(?<exception>[A-Za-z_][\w.$]*(?:Exception|Error))\b"
| stats count AS occurrences latest(_time) AS last_seen BY application exception
| sort - occurrences
| head 10
| convert ctime(last_seen)
```

```spl
index=web sourcetype=access_combined earliest=-24h latest=now status IN (500)
| stats count BY uri status | sort - count | head 20
```

## 5. Remediation
1. Roll back the most recent release if errors started with it.
2. Check upstream dependencies (DB, cache, downstream APIs) and connection pools.
3. Scale out the service if saturation (CPU, threads) is the cause.

### Alert-specific actions
- Identify failing endpoints and hosts.
- Check recent deployments and upstream dependencies.
- Roll back or fail over if the error rate keeps rising.

## 6. Escalation
Page the service owner when the 5xx rate exceeds the SLO error budget burn rate.

## 7. References
- n/a

## 8. Post-incident
- Record root cause and timeline in the incident ticket.
- Tune the threshold / add suppressions if the alert was noisy.
- Update this runbook with anything that would have helped.

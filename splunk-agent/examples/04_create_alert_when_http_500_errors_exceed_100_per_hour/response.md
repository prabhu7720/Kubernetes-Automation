# HTTP Error Responses

- **Request:** Create alert when HTTP 500 errors exceed 100 per hour
- **Artifact:** alert  |  **Matched:** http_status_errors  |  **Confidence:** 100%
- **Threshold:** > 100 per 1h
- **Other candidates:** app_error_trend, http_error_rate

## 1. Generated SPL

Ad-hoc (inline time range):

```spl
index=web sourcetype=access_combined earliest=-24h latest=now status IN (500)
| timechart span=1h count BY status
```

Saved-search form (time range set by schedule/dispatch):

```spl
index=web sourcetype=access_combined status IN (500)
| timechart span=1h count BY status
```

## 2. Explanation

- Use case 'HTTP Error Responses': HTTP responses matching the selected status codes (default 5xx) over time.
- Datasource 'web' resolved to index=web sourcetype=access_combined (selected from the discovered catalog, confidence 100%). Field mapping: status_code->status.
- Retrieves events from index web (sourcetype access_combined) for -24h to now matching: status IN (500).
- `timechart` buckets results over time (span 1h) computing count, one series per status.

## 3. Visualization Recommendation

- **Primary:** line (`splunk.line`)
- **Why:** Time-bucketed series are best read as a trend line.
- **Alternatives:** area, column

## 4. Dashboard Component Suggestions

| Panel | Kind | Studio type | Use case |
|---|---|---|---|
| HTTP Error Responses (total) | kpi | `splunk.singlevalue` | http_status_errors |
| HTTP Error Responses | chart | `splunk.line` | http_status_errors |
| HTTP Error Rate | table | `splunk.table` | http_error_rate |
| Slowest Endpoints | table | `splunk.table` | slowest_endpoints |
| Request Volume by Status Class | chart | `splunk.area` | request_volume |

## 5. Alert Recommendations

**Alert:** HTTP Error Responses
- Severity: **High** (alert.severity=5)
- Threshold: `errors > 100` evaluated over 1h
- Schedule: `0 * * * *` (hourly at :00), window `-1h@h` to `@h`
- Throttle: none
- Recommended actions:
  - Identify failing endpoints and hosts.
  - Check recent deployments and upstream dependencies.
  - Roll back or fail over if the error rate keeps rising.

```spl
index=web sourcetype=access_combined status IN (500)
| stats count AS errors dc(host) AS affected_hosts dc(uri) AS affected_endpoints
| where errors > 100
```

savedsearches.conf:

```ini
[AUTO - Alert - HTTP Error Responses]
action.email.inline = 1
action.email.message.alert = Splunk alert "HTTP Error Responses" fired. \
 \
Condition : errors > 100 \
Severity  : high \
Summary   : HTTP responses matching the selected status codes (default 5xx) over time. \
 \
Recommended actions: \
- Identify failing endpoints and hosts. \
- Check recent deployments and upstream dependencies. \
- Roll back or fail over if the error rate keeps rising. \
 \
Results: $results.link$
action.email.sendresults = 1
action.email.subject = [HIGH] $name$
action.email.to = ${SPLUNK_AGENT_ALERT_EMAIL:-}
action.webhook.param.url = ${SPLUNK_AGENT_ALERT_WEBHOOK:-}
actions = email,webhook
alert.digest_mode = 1
alert.severity = 5
alert.track = 1
alert_comparator = greater than
alert_threshold = 0
alert_type = number of events
cron_schedule = 0 * * * *
description = HTTP responses matching the selected status codes (default 5xx) over time.
dispatch.earliest_time = -1h@h
dispatch.latest_time = @h
is_scheduled = 1
schedule_window = auto
search = index=web sourcetype=access_combined status IN (500) \
| stats count AS errors dc(host) AS affected_hosts dc(uri) AS affected_endpoints \
| where errors > 100
```

## 6. Report Definition

**Report:** HTTP Error Responses
**Description:** Server-side errors directly impact customers and revenue; tracking them protects SLAs.
**Schedule:** `0 6 * * *` (daily at 06:00)
**Time range:** `-24h` to `now`
**Visualization:** line

```spl
index=web sourcetype=access_combined status IN (500)
| timechart span=1h count BY status
```

savedsearches.conf:

```ini
[AUTO - Report - HTTP Error Responses]
cron_schedule = 0 6 * * *
description = HTTP responses matching the selected status codes (default 5xx) over time.
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
search = index=web sourcetype=access_combined status IN (500) \
| timechart span=1h count BY status
```

## Runbook

Runbook written to `runbook_http_error_responses_runbook.md`.

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


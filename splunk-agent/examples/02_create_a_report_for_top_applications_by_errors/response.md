# Top Applications by Error Volume

- **Request:** Create a report for top applications by errors
- **Artifact:** report  |  **Matched:** top_app_errors  |  **Confidence:** 100%
- **Other candidates:** app_error_trend, app_exceptions

## 1. Generated SPL

Ad-hoc (inline time range):

```spl
index=app_logs sourcetype=_json earliest=-24h latest=now level IN ("ERROR", "FATAL", "CRITICAL")
| stats count AS errors BY application
| sort - errors
| head 10
```

Saved-search form (time range set by schedule/dispatch):

```spl
index=app_logs sourcetype=_json level IN ("ERROR", "FATAL", "CRITICAL")
| stats count AS errors BY application
| sort - errors
| head 10
```

## 2. Explanation

- Use case 'Top Applications by Error Volume': Displays applications generating the largest number of errors.
- Datasource 'app_logs' resolved to index=app_logs sourcetype=_json (selected from the discovered catalog, confidence 100%).
- Retrieves events from index app_logs (sourcetype _json) for -24h to now matching: level IN ("ERROR", "FATAL", "CRITICAL").
- `stats` computes count grouped by application.
- `sort` orders results by descending errors.
- `head` keeps the first 10 rows.

## 3. Visualization Recommendation

- **Primary:** column (`splunk.column`)
- **Why:** One category with one measure - ranked column chart.
- **Alternatives:** bar, pie, table

## 4. Dashboard Component Suggestions

| Panel | Kind | Studio type | Use case |
|---|---|---|---|
| Top Applications by Error Volume (total) | kpi | `splunk.singlevalue` | top_app_errors |
| Top Applications by Error Volume | chart | `splunk.column` | top_app_errors |
| Top Applications by Error Volume - Trend | chart | `splunk.line` | top_app_errors |
| Application Error Trend | chart | `splunk.line` | app_error_trend |
| Top Application Exceptions | table | `splunk.table` | app_exceptions |

## 5. Alert Recommendations

**Alert:** Top Applications by Error Volume
- Severity: **Medium** (alert.severity=4)
- Threshold: `errors > 500` evaluated over 1h
- Schedule: `0 * * * *` (hourly at :00), window `-1h@h` to `@h`
- Throttle: application for 1h
- Recommended actions:
  - Open the top error messages for the application.
  - Correlate with recent releases.

```spl
index=app_logs sourcetype=_json level IN ("ERROR", "FATAL", "CRITICAL")
| stats count AS errors BY application
| where errors > 500
```

savedsearches.conf:

```ini
[AUTO - Alert - Top Applications by Error Volume]
action.email.inline = 1
action.email.message.alert = Splunk alert "Top Applications by Error Volume" fired. \
 \
Condition : errors > 500 \
Severity  : medium \
Summary   : Displays applications generating the largest number of errors. \
 \
Recommended actions: \
- Open the top error messages for the application. \
- Correlate with recent releases. \
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
alert.suppress.fields = application
alert.suppress.period = 1h
alert.track = 1
alert_comparator = greater than
alert_threshold = 0
alert_type = number of events
cron_schedule = 0 * * * *
description = Displays applications generating the largest number of errors.
dispatch.earliest_time = -1h@h
dispatch.latest_time = @h
is_scheduled = 1
schedule_window = auto
search = index=app_logs sourcetype=_json level IN ("ERROR", "FATAL", "CRITICAL") \
| stats count AS errors BY application \
| where errors > 500
```

## 6. Report Definition

**Report:** Top Applications by Error Volume
**Description:** Highlights which applications generate the most errors so engineering can prioritise fixes and track release quality.
**Schedule:** `0 7 * * *` (daily at 07:00)
**Time range:** `-24h` to `now`
**Visualization:** column

```spl
index=app_logs sourcetype=_json level IN ("ERROR", "FATAL", "CRITICAL")
| stats count AS errors BY application
| sort - errors
| head 10
```

savedsearches.conf:

```ini
[AUTO - Report - Top Applications by Error Volume]
cron_schedule = 0 7 * * *
description = Displays applications generating the largest number of errors.
dispatch.earliest_time = -24h
dispatch.latest_time = now
display.general.type = visualizations
display.page.search.tab = visualizations
display.visualizations.charting.chart = column
display.visualizations.type = charting
is_scheduled = 1
request.ui_dispatch_app = search
request.ui_dispatch_view = search
schedule_window = auto
search = index=app_logs sourcetype=_json level IN ("ERROR", "FATAL", "CRITICAL") \
| stats count AS errors BY application \
| sort - errors \
| head 10
```

# Failed Logins

- **Request:** Show failed login activity
- **Artifact:** search  |  **Matched:** failed_logins  |  **Confidence:** 100%
- **Other candidates:** brute_force, auth_failure_trend

## 1. Generated SPL

Ad-hoc (inline time range):

```spl
((index=auth sourcetype=linux_secure) OR (index=wineventlog sourcetype="WinEventLog:Security")) earliest=-24h latest=now action IN ("failure", "failed", "fail")
| stats count AS failures dc(src) AS distinct_sources values(src) AS sources latest(_time) AS last_seen BY user
| sort - failures
| head 25
| convert ctime(last_seen)
```

Saved-search form (time range set by schedule/dispatch):

```spl
((index=auth sourcetype=linux_secure) OR (index=wineventlog sourcetype="WinEventLog:Security")) action IN ("failure", "failed", "fail")
| stats count AS failures dc(src) AS distinct_sources values(src) AS sources latest(_time) AS last_seen BY user
| sort - failures
| head 25
| convert ctime(last_seen)
```

Accelerated (tstats on CIM data model):

```spl
| tstats summariesonly=true count AS failures dc(Authentication.src) AS distinct_sources FROM datamodel=Authentication WHERE Authentication.action="failure" earliest=-24h latest=now BY Authentication.user
| rename Authentication.* AS *
| sort - failures
| head 25
```

## 2. Explanation

- Use case 'Failed Logins': Failed authentication attempts aggregated by account with source context.
- Datasource 'authentication' resolved to index=auth sourcetype=linux_secure; index=wineventlog sourcetype="WinEventLog:Security" (selected from the discovered catalog, confidence 100%).
- Retrieves events from index auth, wineventlog (sourcetype linux_secure, WinEventLog:Security) for -24h to now matching: ( action IN ("failure", "failed", "fail").
- `stats` computes count, dc(src) as distinct_sources, values(src) as sources, latest(_time) as last_seen grouped by user.
- `sort` orders results by descending failures.
- `head` keeps the first 25 rows.
- `convert` formats ctime(last_seen) as human-readable time.
- The 'Authentication' data model is accelerated - the tstats variant returns the same answer far faster.

## 3. Visualization Recommendation

- **Primary:** table (`splunk.table`)
- **Why:** 1 dimension(s) and 3 measure(s) - a table preserves detail.
- **Alternatives:** column

## 4. Dashboard Component Suggestions

| Panel | Kind | Studio type | Use case |
|---|---|---|---|
| Failed Logins (total) | kpi | `splunk.singlevalue` | failed_logins |
| Failed Logins | table | `splunk.table` | failed_logins |
| Failed Logins - Trend | chart | `splunk.line` | failed_logins |
| Brute Force Attack Detection | table | `splunk.table` | brute_force |
| Account Lockouts | table | `splunk.table` | account_lockouts |
| Authentication Failure Trend | chart | `splunk.line` | auth_failure_trend |

## 5. Alert Recommendations

**Alert:** Failed Logins
- Severity: **Medium** (alert.severity=4)
- Threshold: `failures > 10` evaluated over 15m
- Schedule: `*/15 * * * *` (every 15 minutes), window `-15m@m` to `@m`
- Throttle: user for 1h
- Recommended actions:
  - Validate whether the account owner initiated the attempts.
  - Check source IPs against threat intel and VPN/geo baselines.
  - Lock or reset credentials if compromise is suspected.

```spl
((index=auth sourcetype=linux_secure) OR (index=wineventlog sourcetype="WinEventLog:Security")) action IN ("failure", "failed", "fail")
| stats count AS failures dc(src) AS distinct_sources values(src) AS sources BY user
| where failures > 10
```

savedsearches.conf:

```ini
[AUTO - Alert - Failed Logins]
action.email.inline = 1
action.email.message.alert = Splunk alert "Failed Logins" fired. \
 \
Condition : failures > 10 \
Severity  : medium \
Summary   : Failed authentication attempts aggregated by account with source context. \
 \
Recommended actions: \
- Validate whether the account owner initiated the attempts. \
- Check source IPs against threat intel and VPN/geo baselines. \
- Lock or reset credentials if compromise is suspected. \
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
alert.suppress.fields = user
alert.suppress.period = 1h
alert.track = 1
alert_comparator = greater than
alert_threshold = 0
alert_type = number of events
cron_schedule = */15 * * * *
description = Failed authentication attempts aggregated by account with source context.
dispatch.earliest_time = -15m@m
dispatch.latest_time = @m
is_scheduled = 1
schedule_window = auto
search = ((index=auth sourcetype=linux_secure) OR (index=wineventlog sourcetype="WinEventLog:Security")) action IN ("failure", "failed", "fail") \
| stats count AS failures dc(src) AS distinct_sources values(src) AS sources BY user \
| where failures > 10
```

## 6. Report Definition

**Report:** Failed Logins
**Description:** Detects credential misuse early and evidences access-control monitoring for audits.
**Schedule:** `0 6 * * *` (daily at 06:00)
**Time range:** `-24h` to `now`
**Visualization:** table

```spl
((index=auth sourcetype=linux_secure) OR (index=wineventlog sourcetype="WinEventLog:Security")) action IN ("failure", "failed", "fail")
| stats count AS failures dc(src) AS distinct_sources values(src) AS sources latest(_time) AS last_seen BY user
| sort - failures
| head 25
| convert ctime(last_seen)
```

savedsearches.conf:

```ini
[AUTO - Report - Failed Logins]
cron_schedule = 0 6 * * *
description = Failed authentication attempts aggregated by account with source context.
dispatch.earliest_time = -24h
dispatch.latest_time = now
display.general.type = statistics
display.page.search.tab = statistics
is_scheduled = 1
request.ui_dispatch_app = search
request.ui_dispatch_view = search
schedule_window = auto
search = ((index=auth sourcetype=linux_secure) OR (index=wineventlog sourcetype="WinEventLog:Security")) action IN ("failure", "failed", "fail") \
| stats count AS failures dc(src) AS distinct_sources values(src) AS sources latest(_time) AS last_seen BY user \
| sort - failures \
| head 25 \
| convert ctime(last_seen)
```

## Warnings

- Existing report 'Daily Failed Logins Summary' (app search) looks similar - consider reusing it.

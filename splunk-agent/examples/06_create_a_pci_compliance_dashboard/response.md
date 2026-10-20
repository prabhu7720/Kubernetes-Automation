# PCI DSS Compliance Overview

- **Request:** Create a PCI compliance dashboard
- **Artifact:** dashboard  |  **Matched:** pci_failed_access, pci_audit_log_changes, pci_account_management, pci_antivirus_detections, pci_privileged_activity, pci_default_accounts, pci_firewall_changes  |  **Confidence:** 100%

## 1. Generated SPL

Ad-hoc (inline time range):

```spl
((index=auth sourcetype=linux_secure) OR (index=wineventlog sourcetype="WinEventLog:Security")) earliest=-24h latest=now action IN ("failure", "failed", "fail")
| stats count AS failures dc(user) AS accounts BY dest
| sort - failures
```

Saved-search form (time range set by schedule/dispatch):

```spl
((index=auth sourcetype=linux_secure) OR (index=wineventlog sourcetype="WinEventLog:Security")) action IN ("failure", "failed", "fail")
| stats count AS failures dc(user) AS accounts BY dest
| sort - failures
```

_11 panel searches are included in the dashboard definition and JSON output._

## 2. Explanation

- Dashboard blueprint 'pci_compliance' selected with 11 panels; panels share a global time picker.
- Use case 'PCI 10.2.4 - Invalid Logical Access Attempts': Failed access attempts to in-scope systems.
- Datasource 'authentication' resolved to index=auth sourcetype=linux_secure; index=wineventlog sourcetype="WinEventLog:Security" (selected from the discovered catalog, confidence 100%).
- Retrieves events from index auth, wineventlog (sourcetype linux_secure, WinEventLog:Security) for -24h to now matching: ( action IN ("failure", "failed", "fail").
- `stats` computes count, dc(user) as accounts grouped by dest.
- `sort` orders results by descending failures.

## 3. Visualization Recommendation

- **Primary:** table (`splunk.table`)
- **Why:** Rule pack recommends table. Shape analysis: One category with one measure - ranked column chart.
- **Alternatives:** column, bar, pie

## 4. Dashboard Component Suggestions

| Panel | Kind | Studio type | Use case |
|---|---|---|---|
| Failed Access Attempts (10.2.4) | kpi | `splunk.singlevalue` | pci_failed_access |
| Audit Log Changes (10.2.6) | kpi | `splunk.singlevalue` | pci_audit_log_changes |
| Account Changes (8.2) | kpi | `splunk.singlevalue` | pci_account_management |
| Malware Detections (5.2) | kpi | `splunk.singlevalue` | pci_antivirus_detections |
| Failed Access Trend | chart | `splunk.line` | pci_failed_access |
| Account Changes by Event Code | chart | `splunk.column` | pci_account_management |
| Administrative Actions (10.2.2) | table | `splunk.table` | pci_privileged_activity |
| Default Account Usage (2.2.2) | table | `splunk.table` | pci_default_accounts |
| Network Control Changes (1.2) | table | `splunk.table` | pci_firewall_changes |
| Audit Log Change Details | table | `splunk.table` | pci_audit_log_changes |
| Failed Access by System | table | `splunk.table` | pci_failed_access |

## 5. Alert Recommendations

**Alert:** PCI 10.2.4 - Invalid Logical Access Attempts
- Severity: **Medium** (alert.severity=4)
- Threshold: `failures > 25` evaluated over 1h
- Schedule: `0 * * * *` (hourly at :00), window `-1h@h` to `@h`
- Throttle: none
- Recommended actions:
  - Review the matching results and confirm the condition is genuine.
  - Identify the owning team / asset and notify them.
  - Document findings and tune the threshold if this is noise.

```spl
((index=auth sourcetype=linux_secure) OR (index=wineventlog sourcetype="WinEventLog:Security")) action IN ("failure", "failed", "fail")
| stats count AS failures dc(user) AS accounts BY dest
| sort - failures
| where failures > 25
```

**Alert:** PCI 10.2.6 - Audit Log Changes
- Severity: **Critical** (alert.severity=6)
- Threshold: `count > 0` evaluated over 15m
- Schedule: `*/15 * * * *` (every 15 minutes), window `-15m@m` to `@m`
- Throttle: none
- Recommended actions:
  - Review the matching results and confirm the condition is genuine.
  - Identify the owning team / asset and notify them.
  - Document findings and tune the threshold if this is noise.

```spl
index=wineventlog sourcetype="WinEventLog:Security" EventCode IN (1102, 104, 4719, 4906, 4907)
| stats count BY dest user EventCode
| where count > 0
```

**Alert:** PCI 2.2.2 - Vendor Default Account Usage
- Severity: **High** (alert.severity=5)
- Threshold: `logins > 0` evaluated over 1h
- Schedule: `0 * * * *` (hourly at :00), window `-1h@h` to `@h`
- Throttle: none
- Recommended actions:
  - Review the matching results and confirm the condition is genuine.
  - Identify the owning team / asset and notify them.
  - Document findings and tune the threshold if this is noise.

```spl
((index=auth sourcetype=linux_secure) OR (index=wineventlog sourcetype="WinEventLog:Security")) action="success" user IN ("admin", "administrator", "root", "guest", "sa", "default", "test")
| stats count AS logins values(src) AS sources BY user dest
| sort - logins
| where logins > 0
```

savedsearches.conf:

```ini
[AUTO - Alert - PCI 10.2.4 - Invalid Logical Access Attempts]
action.email.inline = 1
action.email.message.alert = Splunk alert "PCI 10.2.4 - Invalid Logical Access Attempts" fired. \
 \
Condition : failures > 25 \
Severity  : medium \
Summary   : Failed access attempts to in-scope systems. \
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
alert.track = 1
alert_comparator = greater than
alert_threshold = 0
alert_type = number of events
cron_schedule = 0 * * * *
description = Failed access attempts to in-scope systems.
dispatch.earliest_time = -1h@h
dispatch.latest_time = @h
is_scheduled = 1
schedule_window = auto
search = ((index=auth sourcetype=linux_secure) OR (index=wineventlog sourcetype="WinEventLog:Security")) action IN ("failure", "failed", "fail") \
| stats count AS failures dc(user) AS accounts BY dest \
| sort - failures \
| where failures > 25

[AUTO - Alert - PCI 10.2.6 - Audit Log Changes]
action.email.inline = 1
action.email.message.alert = Splunk alert "PCI 10.2.6 - Audit Log Changes" fired. \
 \
Condition : count > 0 \
Severity  : critical \
Summary   : Clearing of audit logs and audit-policy changes. \
 \
Recommended actions: \
- Review the matching results and confirm the condition is genuine. \
- Identify the owning team / asset and notify them. \
- Document findings and tune the threshold if this is noise. \
 \
Results: $results.link$
action.email.sendresults = 1
action.email.subject = [CRITICAL] $name$
action.email.to = ${SPLUNK_AGENT_ALERT_EMAIL:-}
action.webhook.param.url = ${SPLUNK_AGENT_ALERT_WEBHOOK:-}
actions = email,webhook
alert.digest_mode = 1
alert.severity = 6
alert.track = 1
alert_comparator = greater than
alert_threshold = 0
alert_type = number of events
cron_schedule = */15 * * * *
description = Clearing of audit logs and audit-policy changes.
dispatch.earliest_time = -15m@m
dispatch.latest_time = @m
is_scheduled = 1
schedule_window = auto
search = index=wineventlog sourcetype="WinEventLog:Security" EventCode IN (1102, 104, 4719, 4906, 4907) \
| stats count BY dest user EventCode \
| where count > 0

[AUTO - Alert - PCI 2.2.2 - Vendor Default Account Usage]
action.email.inline = 1
action.email.message.alert = Splunk alert "PCI 2.2.2 - Vendor Default Account Usage" fired. \
 \
Condition : logins > 0 \
Severity  : high \
Summary   : Successful logins with vendor-default or generic accounts. \
 \
Recommended actions: \
- Review the matching results and confirm the condition is genuine. \
- Identify the owning team / asset and notify them. \
- Document findings and tune the threshold if this is noise. \
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
description = Successful logins with vendor-default or generic accounts.
dispatch.earliest_time = -1h@h
dispatch.latest_time = @h
is_scheduled = 1
schedule_window = auto
search = ((index=auth sourcetype=linux_secure) OR (index=wineventlog sourcetype="WinEventLog:Security")) action="success" user IN ("admin", "administrator", "root", "guest", "sa", "default", "test") \
| stats count AS logins values(src) AS sources BY user dest \
| sort - logins \
| where logins > 0
```

## 6. Report Definition

**Report:** PCI 10.2.4 - Invalid Logical Access Attempts
**Description:** PCI 10.2.4 - Invalid Logical Access Attempts provides PCI DSS evidence for assessors (QSA): Failed access attempts to in-scope systems.
**Schedule:** `0 6 * * *` (daily at 06:00)
**Time range:** `-24h` to `now`
**Visualization:** table

```spl
((index=auth sourcetype=linux_secure) OR (index=wineventlog sourcetype="WinEventLog:Security")) action IN ("failure", "failed", "fail")
| stats count AS failures dc(user) AS accounts BY dest
| sort - failures
```

savedsearches.conf:

```ini
[AUTO - Report - PCI 10.2.4 - Invalid Logical Access Attempts]
cron_schedule = 0 6 * * *
description = Failed access attempts to in-scope systems.
dispatch.earliest_time = -24h
dispatch.latest_time = now
display.general.type = statistics
display.page.search.tab = statistics
is_scheduled = 1
request.ui_dispatch_app = search
request.ui_dispatch_view = search
schedule_window = auto
search = ((index=auth sourcetype=linux_secure) OR (index=wineventlog sourcetype="WinEventLog:Security")) action IN ("failure", "failed", "fail") \
| stats count AS failures dc(user) AS accounts BY dest \
| sort - failures
```

## Dashboard

**Dashboard Studio:** PCI DSS Compliance Overview (`auto_pci_dss_compliance_overview`), 11 panels, global time picker + drilldowns.

| Panel | Kind | Type | Use case |
|---|---|---|---|
| Failed Access Attempts (10.2.4) | kpi | `splunk.singlevalue` | pci_failed_access |
| Audit Log Changes (10.2.6) | kpi | `splunk.singlevalue` | pci_audit_log_changes |
| Account Changes (8.2) | kpi | `splunk.singlevalue` | pci_account_management |
| Malware Detections (5.2) | kpi | `splunk.singlevalue` | pci_antivirus_detections |
| Failed Access Trend | chart | `splunk.line` | pci_failed_access |
| Account Changes by Event Code | chart | `splunk.column` | pci_account_management |
| Administrative Actions (10.2.2) | table | `splunk.table` | pci_privileged_activity |
| Default Account Usage (2.2.2) | table | `splunk.table` | pci_default_accounts |
| Network Control Changes (1.2) | table | `splunk.table` | pci_firewall_changes |
| Audit Log Change Details | table | `splunk.table` | pci_audit_log_changes |
| Failed Access by System | table | `splunk.table` | pci_failed_access |

Full definition written to `dashboard_<name>.json` (Studio source) and `.xml` (deployable view).

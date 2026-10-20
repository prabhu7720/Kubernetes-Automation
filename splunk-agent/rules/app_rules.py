"""Application / web rule pack: errors, HTTP status, latency, traffic."""

from __future__ import annotations

from core.models import AlertSpec, InputSpec, PanelSpec, RunbookSpec, Severity, Visualization as V
from rules.base import RulePack

_HTTP_RUNBOOK = RunbookSpec(
    triage=("Which hosts/endpoints are returning errors and since when?",
            "Did a deployment, config change or dependency incident coincide with the spike?"),
    investigation=("uc:slowest_endpoints", "uc:app_exceptions",
                   "| stats count BY {{f.uri}} {{f.status_code}} | sort - count | head 20"),
    remediation=("Roll back the most recent release if errors started with it.",
                 "Check upstream dependencies (DB, cache, downstream APIs) and connection pools.",
                 "Scale out the service if saturation (CPU, threads) is the cause."),
    escalation="Page the service owner when the 5xx rate exceeds the SLO error budget burn rate.",
)


class ApplicationRules(RulePack):
    domain = "application"
    title = "Application & Web"
    description = "Application errors, HTTP status codes, latency and traffic."
    domain_keywords = ("application", "service", "api", "http", "web", "latency", "request", "endpoint",
                       "microservice", "website", "apm")

    def use_cases(self):
        return [
            self.uc(
                "top_app_errors", "Top Applications by Error Volume",
                description="Displays applications generating the largest number of errors.",
                datasource="app_logs",
                keywords=("top application error", "application error", "error volume", "most error",
                          "error by application", "noisy application"),
                filter='{{f.level}} IN ("ERROR", "FATAL", "CRITICAL")',
                pipeline="""
| stats count AS errors BY {{groupby}}
| sort - errors
| head {{limit}}""",
                groupby="application", visualization=V.COLUMN, report_cron="0 7 * * *",
                single_value="| stats count AS errors",
                alert=AlertSpec(threshold=500, metric="errors", severity=Severity.MEDIUM, window="1h",
                                pipeline="| stats count AS errors BY {{f.application}}",
                                throttle_fields=("application",),
                                recommended_actions=("Open the top error messages for the application.",
                                                     "Correlate with recent releases.")),
                related=("app_error_trend", "app_exceptions"),
                business_value="Highlights which applications generate the most errors so engineering can "
                               "prioritise fixes and track release quality.",
            ),
            self.uc(
                "app_error_trend", "Application Error Trend",
                description="Error volume over time per application.",
                datasource="app_logs",
                keywords=("error trend", "error over time", "error timeline", "application error trend"),
                filter='{{f.level}} IN ("ERROR", "FATAL", "CRITICAL")',
                pipeline="| timechart span={{span}} count AS errors BY {{groupby}} limit={{limit}} useother=true",
                groupby="application", visualization=V.LINE,
            ),
            self.uc(
                "http_status_errors", "HTTP Error Responses",
                description="HTTP responses matching the selected status codes (default 5xx) over time.",
                datasource="web",
                keywords=("http error", "http 500", "5xx", "server error", "http status", "500 error",
                          "internal server error", "statuscode error", "http failure", "http 500 trend"),
                filter="{{f.status_code}} IN ({{p.status}})",
                params={"status": "5*"},
                pipeline="| timechart span={{span}} count BY {{f.status_code}}",
                visualization=V.LINE,
                single_value="| stats count AS http_errors",
                alert=AlertSpec(threshold=100, metric="errors", severity=Severity.HIGH, window="1h",
                                pipeline="| stats count AS errors dc({{f.host}}) AS affected_hosts dc({{f.uri}}) AS affected_endpoints",
                                recommended_actions=("Identify failing endpoints and hosts.",
                                                     "Check recent deployments and upstream dependencies.",
                                                     "Roll back or fail over if the error rate keeps rising.")),
                related=("http_error_rate", "slowest_endpoints", "request_volume"),
                business_value="Server-side errors directly impact customers and revenue; tracking them protects SLAs.",
                runbook=_HTTP_RUNBOOK,
            ),
            self.uc(
                "http_error_rate", "HTTP Error Rate",
                description="Percentage of 5xx responses per host.",
                datasource="web",
                keywords=("error rate", "failure rate", "http error rate", "error percentage", "5xx rate",
                          "availability"),
                filter="{{f.status_code}}=*",
                pipeline="""
| stats count AS requests count(eval(tonumber({{q.status_code}}) >= 500)) AS server_errors BY {{groupby}}
| eval error_rate_pct=round(server_errors / requests * 100, 2)
| where requests >= 20
| sort - error_rate_pct
| head {{limit}}""",
                groupby="host", visualization=V.TABLE,
                single_value="""
| stats count AS requests count(eval(tonumber({{q.status_code}}) >= 500)) AS errors
| eval error_rate_pct=round(errors / requests * 100, 2)
| fields error_rate_pct""",
                alert=AlertSpec(threshold=5, metric="error_rate_pct", severity=Severity.HIGH, window="15m",
                                throttle_fields=("host",)),
                runbook=_HTTP_RUNBOOK,
            ),
            self.uc(
                "service_latency", "Service Latency (p95)",
                description="95th percentile response time per service over time.",
                datasource="app_logs",
                keywords=("latency", "service latency", "p95", "slow request", "performance", "latency trend",
                          "p99", "api latency"),
                filter="{{f.response_time}}=*",
                pipeline="| timechart span={{span}} perc95({{f.response_time}}) AS p95_latency BY {{groupby}} limit={{limit}}",
                groupby="application", default_span="5m", visualization=V.LINE,
                single_value="| stats perc95({{f.response_time}}) AS p95_latency\n| eval p95_latency=round(p95_latency, 0)",
                alert=AlertSpec(threshold=1000, metric="p95_latency", severity=Severity.HIGH, window="15m",
                                pipeline="""
| stats perc95({{f.response_time}}) AS p95_latency avg({{f.response_time}}) AS avg_latency count AS requests BY {{f.application}}
| eval p95_latency=round(p95_latency, 2), avg_latency=round(avg_latency, 2)""",
                                throttle_fields=("application",),
                                recommended_actions=("Check dependency latency (DB, cache, downstream APIs).",
                                                     "Look for GC pauses, thread pool or connection pool exhaustion.")),
                related=("slowest_endpoints",),
            ),
            self.uc(
                "slowest_endpoints", "Slowest Endpoints",
                description="Endpoints ranked by p95 response time.",
                datasource="web",
                keywords=("slowest endpoint", "latency endpoint", "latency api", "slowest uri", "slowest request",
                          "slowest page"),
                filter="{{f.response_time}}=*",
                pipeline="""
| stats count AS requests avg({{f.response_time}}) AS avg_ms perc95({{f.response_time}}) AS p95_ms BY {{f.uri}}
| where requests >= 10
| eval avg_ms=round(avg_ms, 2), p95_ms=round(p95_ms, 2)
| sort - p95_ms
| head {{limit}}""",
                visualization=V.TABLE,
            ),
            self.uc(
                "app_exceptions", "Top Application Exceptions",
                description="Most frequent exception classes per application.",
                datasource="app_logs",
                keywords=("exception", "stack trace", "traceback", "top exception", "application exception",
                          "java exception"),
                filter='(Exception OR Traceback OR "stack trace")',
                pipeline=r"""
| rex field=_raw "(?<exception>[A-Za-z_][\w.$]*(?:Exception|Error))\b"
| stats count AS occurrences latest(_time) AS last_seen BY {{groupby}} exception
| sort - occurrences
| head {{limit}}
| convert ctime(last_seen)""",
                groupby="application", visualization=V.TABLE,
            ),
            self.uc(
                "request_volume", "Request Volume by Status Class",
                description="Web request throughput split by 2xx/3xx/4xx/5xx.",
                datasource="web",
                keywords=("request volume", "traffic", "web traffic", "request count", "http traffic",
                          "requests per"),
                filter="{{f.status_code}}=*",
                pipeline="""
| eval status_class=substr(tostring({{q.status_code}}), 1, 1) . "xx"
| timechart span={{span}} count BY status_class""",
                visualization=V.AREA, default_span="15m",
                single_value="| stats count AS requests",
            ),
        ]

    def dashboards(self):
        return [
            self.bp(
                "application_health", "Application Health",
                description="Golden signals: traffic, errors and latency for applications and web tiers.",
                keywords=("application health", "application", "service health", "application performance",
                          "api health", "web health", "apm", "golden signal"),
                inputs=(InputSpec("application", "Application", "application"),),
                panels=(
                    PanelSpec("request_volume", "Requests", V.SINGLE),
                    PanelSpec("http_status_errors", "HTTP 5xx", V.SINGLE),
                    PanelSpec("http_error_rate", "5xx Error Rate %", V.SINGLE),
                    PanelSpec("service_latency", "p95 Latency (ms)", V.SINGLE),
                    PanelSpec("request_volume", "Traffic by Status Class"),
                    PanelSpec("http_status_errors", "HTTP Errors Over Time"),
                    PanelSpec("service_latency", "p95 Latency by Service"),
                    PanelSpec("top_app_errors", "Top Applications by Errors"),
                    PanelSpec("slowest_endpoints", "Slowest Endpoints"),
                    PanelSpec("app_exceptions", "Top Exceptions"),
                    PanelSpec("http_error_rate", "Error Rate by Host"),
                ),
            ),
        ]

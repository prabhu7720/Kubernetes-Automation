"""Infrastructure rule pack: hosts, OS resources, DNS, firewall, syslog."""

from __future__ import annotations

from core.models import AlertSpec, PanelSpec, RunbookSpec, Severity, Visualization as V
from rules.base import RulePack


class InfrastructureRules(RulePack):
    domain = "infrastructure"
    title = "Infrastructure"
    description = "Host resources, data-forwarding health, DNS and network controls."
    domain_keywords = ("infrastructure", "infra", "host", "cpu", "memory", "disk", "linux", "unix", "windows",
                       "os", "dns", "network", "firewall", "syslog", "filesystem", "forwarder")

    def use_cases(self):
        return [
            self.uc(
                "host_cpu_utilization", "Host CPU Utilization",
                description="CPU used % per host (Splunk Add-on for Unix and Linux 'cpu' sourcetype).",
                datasource="os_cpu",
                keywords=("cpu utilization", "high cpu", "cpu load", "processor utilization", "host cpu"),
                filter='{{f.cpu_id}}="all"',
                pipeline="""
| eval cpu_used_pct=round(100 - tonumber({{q.cpu_idle}}), 2)
| timechart span={{span}} avg(cpu_used_pct) AS avg_cpu_pct BY {{f.host}} limit={{limit}}""",
                default_span="5m", visualization=V.LINE,
                single_value="| eval cpu_used_pct=100 - tonumber({{q.cpu_idle}})\n| stats avg(cpu_used_pct) AS avg_cpu_pct\n| eval avg_cpu_pct=round(avg_cpu_pct, 1)",
                alert=AlertSpec(threshold=90, metric="avg_cpu_pct", severity=Severity.HIGH, window="15m",
                                pipeline="""
| eval cpu_used_pct=100 - tonumber({{q.cpu_idle}})
| stats avg(cpu_used_pct) AS avg_cpu_pct max(cpu_used_pct) AS peak_cpu_pct BY {{f.host}}
| eval avg_cpu_pct=round(avg_cpu_pct, 2)""",
                                throttle_fields=("host",),
                                recommended_actions=("Identify top processes: top -o %CPU / ps aux --sort=-%cpu | head",
                                                     "Check for runaway jobs, deploys or traffic spikes.",
                                                     "Scale the service or right-size the instance.")),
                related=("host_memory_utilization", "disk_space"),
            ),
            self.uc(
                "host_memory_utilization", "Host Memory Utilization",
                description="Memory used % per host (vmstat).",
                datasource="os_memory",
                keywords=("memory utilization", "high memory", "memory pressure", "host memory", "memory host"),
                filter="{{f.mem_used_pct}}=*",
                pipeline="| timechart span={{span}} avg({{f.mem_used_pct}}) AS mem_used_pct BY {{f.host}} limit={{limit}}",
                default_span="5m", visualization=V.LINE,
                alert=AlertSpec(threshold=90, metric="mem_used_pct", severity=Severity.HIGH, window="15m",
                                pipeline="| stats avg({{f.mem_used_pct}}) AS mem_used_pct BY {{f.host}}",
                                throttle_fields=("host",),
                                recommended_actions=("Check top memory consumers: ps aux --sort=-%mem | head",
                                                     "Look for OOM-killer messages: dmesg -T | grep -i oom")),
                related=("host_cpu_utilization",),
            ),
            self.uc(
                "disk_space", "Low Disk Space",
                description="Filesystems above the used-% threshold (df).",
                datasource="os_disk",
                keywords=("disk space", "disk full", "filesystem", "disk utilization", "low disk",
                          "storage utilization", "filesystem full"),
                filter="{{f.disk_used_pct}}=*",
                pipeline="""
| eval used_pct=tonumber(replace({{q.disk_used_pct}}, "%", ""))
| stats latest(used_pct) AS used_pct latest({{f.disk_avail}}) AS available BY {{f.host}} {{f.mount}}
| where used_pct >= {{threshold}}
| sort - used_pct""",
                visualization=V.TABLE,
                single_value="""
| eval used_pct=tonumber(replace({{q.disk_used_pct}}, "%", ""))
| stats latest(used_pct) AS used_pct BY {{f.host}} {{f.mount}}
| where used_pct >= {{threshold}}
| stats count AS filesystems_at_risk""",
                alert=AlertSpec(threshold=85, metric="used_pct", comparator=">=", severity=Severity.HIGH,
                                window="1h", throttle_fields=("host", "mount"),
                                recommended_actions=("du -xh --max-depth=2 <mount> | sort -h | tail",
                                                     "Rotate/compress logs, prune container images (crictl rmi --prune).",
                                                     "Extend the volume if growth is organic.")),
                runbook=RunbookSpec(
                    triage=("Which mount point and how fast is it growing?",),
                    remediation=("journalctl --vacuum-size=500M", "logrotate -f /etc/logrotate.conf",
                                 "Expand EBS/managed disk and grow the filesystem (xfs_growfs / resize2fs)."),
                    escalation="Escalate if >95% on a database or root filesystem."),
            ),
            self.uc(
                "host_not_reporting", "Hosts Not Reporting",
                description="Hosts that stopped sending data (forwarder down, network issue, decommissioned).",
                datasource="any", kind="raw",
                keywords=("notreporting", "notreporting host", "missing host", "silent host", "host down",
                          "forwarder down", "host offline", "stale host"),
                pipeline="""
| tstats latest(_time) AS last_seen WHERE {{index}} {{time}} BY host
| eval minutes_silent=round((now() - last_seen) / 60, 0)
| where minutes_silent >= {{threshold}}
| sort - minutes_silent
| convert ctime(last_seen)""",
                default_earliest="-24h",
                alert=AlertSpec(threshold=60, metric="minutes_silent", comparator=">=", severity=Severity.HIGH,
                                window="1h", lookback="-24h", throttle_fields=("host",),
                                recommended_actions=("Check splunkd on the forwarder: systemctl status SplunkForwarder",
                                                     "Verify connectivity to indexers (port 9997) and deployment server.",
                                                     "Confirm whether the host was decommissioned.")),
            ),
            self.uc(
                "dns_failures", "DNS Failures",
                description="NXDOMAIN/SERVFAIL/REFUSED responses by query and client.",
                datasource="dns",
                keywords=("dns failure", "nxdomain", "servfail", "dns error", "dns resolution failure", "fail dns"),
                filter='{{f.reply_code}} IN ("NXDOMAIN", "SERVFAIL", "REFUSED")',
                pipeline="""
| stats count AS failures dc({{f.src}}) AS clients BY {{f.query}} {{f.reply_code}}
| sort - failures
| head {{limit}}""",
                default_limit=25,
                tstats="""| tstats summariesonly=true count AS failures FROM datamodel=Network_Resolution WHERE (DNS.reply_code="NXDOMAIN" OR DNS.reply_code="SERVFAIL" OR DNS.reply_code="REFUSED") {{time}} BY DNS.query DNS.reply_code
| rename DNS.* AS *
| sort - failures
| head {{limit}}""",
                single_value="| stats count AS dns_failures",
                alert=AlertSpec(threshold=500, metric="failures", severity=Severity.MEDIUM, window="15m",
                                pipeline="| stats count AS failures BY {{f.reply_code}}",
                                recommended_actions=("Check resolver health (CoreDNS/BIND/Infoblox) and upstream forwarders.",
                                                     "High NXDOMAIN from one client may indicate DGA malware.")),
            ),
            self.uc(
                "syslog_errors", "Syslog Errors",
                description="Error/critical/kernel messages from Linux syslog by host and process.",
                datasource="syslog",
                keywords=("syslog error", "kernel error", "system error", "segfault", "kernel panic", "os error",
                          "linux error"),
                filter='(error OR critical OR fatal OR panic OR segfault OR "Out of memory")',
                pipeline="""
| stats count AS errors latest(_raw) AS sample BY {{f.host}} {{f.process}}
| sort - errors
| head {{limit}}""",
                alert=AlertSpec(threshold=100, metric="errors", severity=Severity.MEDIUM, window="15m"),
            ),
            self.uc(
                "firewall_denies", "Firewall Denies",
                description="Blocked/denied connections by source, destination and port.",
                datasource="network_traffic",
                keywords=("firewall deny", "deny traffic", "firewall block", "deny connection", "network deny",
                          "blocked traffic"),
                filter='{{f.action}} IN ("blocked", "deny", "denied", "drop", "dropped", "reset-both")',
                pipeline="""
| stats count AS denies BY {{f.src}} {{f.dest}} {{f.dest_port}}
| sort - denies
| head {{limit}}""",
                default_limit=25,
                alert=AlertSpec(threshold=1000, metric="denies", severity=Severity.MEDIUM, window="15m",
                                pipeline="| stats count AS denies BY {{f.src}}"),
            ),
        ]

    def dashboards(self):
        return [
            self.bp(
                "infrastructure_health", "Infrastructure Health",
                description="Host resources, data forwarding, DNS and firewall activity.",
                keywords=("infrastructure", "infrastructure health", "host health", "infra",
                          "os health", "system health", "linux health"),
                panels=(
                    PanelSpec("host_not_reporting", "Hosts Reporting", V.SINGLE,
                              pipeline="| tstats dc(host) AS hosts_reporting WHERE {{index}}"),
                    PanelSpec("host_cpu_utilization", "Average CPU %", V.SINGLE),
                    PanelSpec("disk_space", "Filesystems at Risk", V.SINGLE),
                    PanelSpec("dns_failures", "DNS Failures", V.SINGLE),
                    PanelSpec("host_cpu_utilization", "CPU % by Host"),
                    PanelSpec("host_memory_utilization", "Memory % by Host"),
                    PanelSpec("dns_failures", "DNS Failures by Code", V.LINE,
                              pipeline="| timechart span={{span}} count BY {{f.reply_code}}"),
                    PanelSpec("firewall_denies", "Firewall Denies Over Time", V.AREA,
                              pipeline="| timechart span={{span}} count AS denies"),
                    PanelSpec("disk_space", "Low Disk Space"),
                    PanelSpec("host_not_reporting", "Silent Hosts"),
                    PanelSpec("syslog_errors", "Syslog Errors"),
                ),
            ),
        ]

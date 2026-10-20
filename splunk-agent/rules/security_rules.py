"""Security operations rule pack (authentication, privilege, malware, network threats)."""

from __future__ import annotations

from core.models import AlertSpec, PanelSpec, RunbookSpec, Severity, Visualization as V
from rules.base import RulePack

_FAIL = '{{f.action}} IN ("failure", "failed", "fail")'

_AUTH_RUNBOOK = RunbookSpec(
    triage=(
        "Confirm the affected account(s) and whether they are privileged or service accounts.",
        "Check if the source IPs are internal, VPN, or external; compare against the user's usual locations.",
        "Look for a successful login from the same source after the failures (possible compromise).",
    ),
    investigation=("uc:brute_force_success", "uc:account_lockouts",
                   "| stats count BY {{f.src}} {{f.dest}} | sort - count"),
    remediation=(
        "Force a password reset and revoke active sessions if compromise is suspected.",
        "Block malicious source IPs at the perimeter / WAF.",
        "Enforce MFA for the affected accounts.",
    ),
    escalation="Escalate to the SOC on-call (P2) if a privileged account is involved or a success follows failures.",
    references=("MITRE ATT&CK T1110 - Brute Force",),
)


class SecurityRules(RulePack):
    domain = "security"
    title = "Security Operations"
    description = "Authentication, privilege, malware and network threat detections (CIM-aware)."
    domain_keywords = ("security", "threat", "attack", "soc", "siem", "malicious", "suspicious", "intrusion",
                       "auth", "login")

    def use_cases(self):
        return [
            self.uc(
                "failed_logins", "Failed Logins",
                description="Failed authentication attempts aggregated by account with source context.",
                datasource="authentication",
                keywords=("failed login", "login failure", "authentication failure", "failed authentication",
                          "auth failure", "invalid password", "bad password", "wrong password"),
                filter=_FAIL,
                pipeline="""
| stats count AS failures dc({{f.src}}) AS distinct_sources values({{f.src}}) AS sources latest(_time) AS last_seen BY {{groupby}}
| sort - failures
| head {{limit}}
| convert ctime(last_seen)""",
                groupby="user", default_limit=25, visualization=V.TABLE,
                single_value="| stats count AS failures",
                tstats="""| tstats summariesonly=true count AS failures dc(Authentication.src) AS distinct_sources FROM datamodel=Authentication WHERE Authentication.action="failure" {{time}} BY Authentication.user
| rename Authentication.* AS *
| sort - failures
| head {{limit}}""",
                alert=AlertSpec(
                    threshold=10, metric="failures", severity=Severity.MEDIUM, window="15m",
                    pipeline="| stats count AS failures dc({{f.src}}) AS distinct_sources values({{f.src}}) AS sources BY {{f.user}}",
                    throttle_fields=("user",),
                    recommended_actions=("Validate whether the account owner initiated the attempts.",
                                         "Check source IPs against threat intel and VPN/geo baselines.",
                                         "Lock or reset credentials if compromise is suspected.")),
                security_domain="access", risk_object=("user", "user"), mitre=("T1110",),
                related=("brute_force", "account_lockouts", "auth_failure_trend"),
                business_value="Detects credential misuse early and evidences access-control monitoring for audits.",
                runbook=_AUTH_RUNBOOK,
            ),
            self.uc(
                "auth_failure_trend", "Authentication Failure Trend",
                description="Volume of failed authentications over time to spot spikes and attack waves.",
                datasource="authentication",
                keywords=("authentication failure trend", "failed login trend", "login failure over time",
                          "auth failure trend", "login failure timeline"),
                filter=_FAIL,
                pipeline="| timechart span={{span}} count AS failures",
                visualization=V.LINE, default_span="1h", related=("failed_logins",),
            ),
            self.uc(
                "brute_force", "Brute Force Attack Detection",
                description="Sources generating many failed logins within a short window.",
                datasource="authentication",
                keywords=("bruteforce", "bruteforce attack", "password guessing", "credential stuffing",
                          "many failed login", "repeated login failure"),
                filter=_FAIL,
                pipeline="""
| bin _time span={{span}}
| stats count AS failures dc({{f.user}}) AS targeted_accounts values({{f.user}}) AS accounts BY _time {{f.src}}
| where failures >= {{threshold}}
| sort - failures""",
                default_span="5m", visualization=V.TABLE,
                single_value="""
| bin _time span={{span}}
| stats count AS failures BY _time {{f.src}}
| where failures >= {{threshold}}
| stats dc({{f.src}}) AS attacking_sources""",
                alert=AlertSpec(threshold=20, metric="failures", comparator=">=", severity=Severity.HIGH,
                                window="15m", throttle_fields=("src",),
                                recommended_actions=("Block the source IP if external and not a known scanner.",
                                                     "Check for any successful login from the same source.",
                                                     "Review targeted accounts for lockouts or resets.")),
                correlation=True, security_domain="access", risk_object=("src", "system"), risk_score=60,
                mitre=("T1110", "T1110.001"), related=("brute_force_success", "failed_logins"),
                runbook=_AUTH_RUNBOOK,
            ),
            self.uc(
                "brute_force_success", "Successful Login After Brute Force",
                description="Accounts with many failures followed by a success from the same source - likely compromise.",
                datasource="authentication",
                keywords=("successful bruteforce", "login after failure", "compromised account",
                          "success after failure", "account compromise"),
                filter='{{f.action}} IN ("success", "failure", "failed", "fail")',
                pipeline="""
| stats count(eval({{q.action}}!="success")) AS failures count(eval({{q.action}}="success")) AS successes latest(_time) AS last_seen BY {{f.src}} {{f.user}}
| where failures >= {{threshold}} AND successes > 0
| sort - failures
| convert ctime(last_seen)""",
                alert=AlertSpec(threshold=10, metric="failures", comparator=">=", severity=Severity.CRITICAL,
                                window="1h", throttle_fields=("user", "src"),
                                recommended_actions=("Treat as a probable account compromise.",
                                                     "Disable the account / revoke sessions and tokens.",
                                                     "Hunt for lateral movement from the account.")),
                correlation=True, security_domain="access", risk_object=("user", "user"), risk_score=80,
                mitre=("T1110", "T1078"), related=("brute_force",), runbook=_AUTH_RUNBOOK,
            ),
            self.uc(
                "password_spraying", "Password Spraying",
                description="Single source failing against many distinct accounts.",
                datasource="authentication",
                keywords=("passwordspray", "password spray attack", "many account fail", "spray attack"),
                filter=_FAIL,
                pipeline="""
| stats dc({{f.user}}) AS targeted_accounts count AS failures values({{f.user}}) AS sample_accounts BY {{f.src}}
| where targeted_accounts >= {{threshold}}
| sort - targeted_accounts""",
                alert=AlertSpec(threshold=10, metric="targeted_accounts", comparator=">=", severity=Severity.HIGH,
                                window="1h", throttle_fields=("src",)),
                correlation=True, security_domain="access", risk_object=("src", "system"), risk_score=60,
                mitre=("T1110.003",), related=("brute_force",),
            ),
            self.uc(
                "privilege_escalation", "Privilege Escalation (Windows)",
                description="Special privileges assigned and additions to privileged security groups.",
                datasource="windows_security",
                keywords=("privesc", "admin group", "elevated privilege", "special privilege", "added to admin",
                          "admin right", "privileged group", "group membership change"),
                filter="{{f.event_code}} IN (4672, 4728, 4732, 4756)",
                pipeline="""
| search NOT {{f.user}}="*$"
| eval activity=case({{q.event_code}}=4672, "Special privileges assigned", {{q.event_code}}=4728, "Added to global security group", {{q.event_code}}=4732, "Added to local security group", {{q.event_code}}=4756, "Added to universal security group", true(), "Other")
| stats count AS events values(activity) AS activities latest(_time) AS last_seen BY {{f.user}} {{f.dest}}
| sort - events
| convert ctime(last_seen)""",
                single_value="| search NOT {{f.user}}=\"*$\"\n| stats dc({{f.user}}) AS privileged_accounts",
                alert=AlertSpec(threshold=0, metric="events", severity=Severity.HIGH, window="15m",
                                pipeline="""
| where {{q.event_code}} IN (4728, 4732, 4756)
| stats count AS events values({{f.user}}) AS actors BY {{f.dest}}""",
                                throttle_fields=("dest",),
                                recommended_actions=("Verify the group change against an approved change ticket.",
                                                     "Remove unauthorised members immediately.",
                                                     "Review the actor's recent activity for further escalation.")),
                correlation=True, security_domain="access", risk_object=("user", "user"), risk_score=70,
                mitre=("T1068", "T1098"), related=("linux_sudo_activity", "new_account_created"),
                runbook=RunbookSpec(
                    triage=("Identify who made the change and which group was modified.",
                            "Check for an approved change request."),
                    investigation=("| stats count BY {{f.event_code}} {{f.user}} {{f.dest}}",),
                    remediation=("Revert unauthorised membership.", "Rotate credentials of the actor if suspicious."),
                    escalation="Escalate to Identity & Access Management and SOC lead.",
                    references=("MITRE ATT&CK T1098 - Account Manipulation",)),
            ),
            self.uc(
                "linux_sudo_activity", "Linux sudo / Privileged Command Activity",
                description="sudo executions and failures on Linux hosts.",
                datasource="linux_auth",
                keywords=("sudo", "linux privesc", "sudo command", "root command", "sudo failure"),
                filter="sudo",
                pipeline=r"""
| rex "sudo:\s+(?<sudo_user>\S+)\s+:.*?USER=(?<run_as>\S+)\s*;\s*COMMAND=(?<command>.*)$"
| eval outcome=if(match(_raw, "incorrect password|NOT in sudoers|authentication failure"), "failure", "success")
| stats count AS executions values(command) AS commands values(run_as) AS run_as BY {{f.host}} sudo_user outcome
| sort - executions""",
                alert=AlertSpec(threshold=3, metric="executions", severity=Severity.MEDIUM, window="15m",
                                pipeline=r"""
| search "NOT in sudoers" OR "incorrect password"
| rex "sudo:\s+(?<sudo_user>\S+)\s+:"
| stats count AS executions BY {{f.host}} sudo_user"""),
                mitre=("T1548.003",), security_domain="endpoint",
            ),
            self.uc(
                "account_lockouts", "Account Lockouts",
                description="Accounts locked out (Windows 4740) with the calling computer.",
                datasource="windows_security",
                keywords=("lockout", "account lockout", "locked account", "user lockout"),
                filter="{{f.event_code}}=4740",
                pipeline="""
| stats count AS lockouts latest(_time) AS last_lockout values({{f.src}}) AS caller_hosts BY {{f.user}}
| sort - lockouts
| convert ctime(last_lockout)""",
                single_value="| stats count AS lockouts",
                alert=AlertSpec(threshold=3, metric="lockouts", comparator=">=", severity=Severity.MEDIUM,
                                window="1h", throttle_fields=("user",),
                                recommended_actions=("Identify the caller host (stale credentials, mapped drives, services).",
                                                     "Contact the user / unlock after verification.")),
                related=("failed_logins",),
                runbook=RunbookSpec(
                    triage=("Check whether lockouts come from one caller host (stale credential) or many (attack).",),
                    investigation=("uc:failed_logins",),
                    remediation=("Clear cached credentials on the caller host.", "Unlock account after identity verification."),
                    escalation="Escalate to SOC if more than 5 accounts lock out from one source within an hour."),
            ),
            self.uc(
                "new_account_created", "New Account Created",
                description="New user accounts created (Windows 4720).",
                datasource="windows_security",
                keywords=("account created", "new user", "user created", "new account", "user creation"),
                filter="{{f.event_code}}=4720",
                pipeline="""
| stats count AS created values({{f.user}}) AS created_accounts latest(_time) AS last_seen BY {{f.src_user}} {{f.dest}}
| convert ctime(last_seen)""",
                alert=AlertSpec(threshold=0, metric="created", severity=Severity.LOW, window="1h"),
                mitre=("T1136",), security_domain="access",
            ),
            self.uc(
                "audit_log_cleared", "Audit Log Cleared",
                description="Windows security/system event log cleared (1102 / 104) - classic anti-forensics.",
                datasource="windows_security",
                keywords=("audit log cleared", "log cleared", "event log cleared", "clear security log",
                          "log tampering", "log wiped"),
                filter="{{f.event_code}} IN (1102, 104)",
                pipeline="""
| stats count AS events latest(_time) AS last_seen values({{f.user}}) AS actors BY {{f.dest}}
| convert ctime(last_seen)""",
                alert=AlertSpec(threshold=0, metric="events", severity=Severity.CRITICAL, window="15m",
                                recommended_actions=("Isolate the host pending investigation.",
                                                     "Preserve remaining forensic artefacts.")),
                correlation=True, security_domain="endpoint", risk_object=("dest", "system"), risk_score=80,
                mitre=("T1070.001",),
            ),
            self.uc(
                "malware_detections", "Malware Indicators",
                description="Endpoint protection detections by host with signatures and actions taken.",
                datasource="endpoint",
                keywords=("malware", "malware indicator", "antivirus detection", "edr alert", "malware detection",
                          "ioc", "indicator compromise", "infected host", "malicious file"),
                filter="{{f.signature}}=*",
                pipeline="""
| stats count AS detections values({{f.signature}}) AS signatures values({{f.file_name}}) AS files values({{f.action}}) AS actions latest(_time) AS last_seen BY {{f.dest}}
| sort - detections
| head {{limit}}
| convert ctime(last_seen)""",
                tstats="""| tstats summariesonly=true count AS detections values(Malware_Attacks.signature) AS signatures FROM datamodel=Malware WHERE nodename=Malware_Attacks {{time}} BY Malware_Attacks.dest
| rename Malware_Attacks.* AS *
| sort - detections""",
                single_value="| stats count AS detections",
                alert=AlertSpec(threshold=0, metric="detections", severity=Severity.HIGH, window="15m",
                                pipeline="""
| search NOT {{f.action}} IN ("blocked", "quarantined", "deleted", "cleaned")
| stats count AS detections values({{f.signature}}) AS signatures BY {{f.dest}}""",
                                throttle_fields=("dest",),
                                recommended_actions=("Isolate the host via EDR if the threat was not blocked.",
                                                     "Collect the sample hash and check reputation.",
                                                     "Scan for the same hash across the fleet.")),
                correlation=True, security_domain="endpoint", risk_object=("dest", "system"), risk_score=60,
                mitre=("T1204",),
            ),
            self.uc(
                "suspicious_ip_activity", "Suspicious IP Activity",
                description="External sources touching many hosts/ports, enriched with threat intel when a lookup exists.",
                datasource="network_traffic",
                keywords=("suspicious ip", "malicious ip", "bad ip", "threat intel", "suspicious traffic",
                          "external ip", "known bad", "suspicious connection"),
                filter="{{f.src}}=*",
                pipeline="""
| where NOT (cidrmatch("10.0.0.0/8", {{q.src}}) OR cidrmatch("172.16.0.0/12", {{q.src}}) OR cidrmatch("192.168.0.0/16", {{q.src}}) OR cidrmatch("127.0.0.0/8", {{q.src}}))
| stats count AS connections dc({{f.dest}}) AS unique_destinations dc({{f.dest_port}}) AS unique_ports values({{f.action}}) AS actions BY {{f.src}}
{{enrich.threat_intel}}
| where unique_destinations >= {{threshold}} OR unique_ports >= {{threshold}} OR isnotnull(threat_category)
| sort - connections
| head {{limit}}""",
                default_limit=50,
                alert=AlertSpec(threshold=50, metric="connections", severity=Severity.HIGH, window="1h",
                                throttle_fields=("src",),
                                recommended_actions=("Block the IP at the firewall if confirmed malicious.",
                                                     "Identify internal hosts that accepted connections.")),
                correlation=True, security_domain="network", risk_object=("src", "system"), risk_score=50,
                mitre=("T1046", "T1071"), related=("port_scan",),
            ),
            self.uc(
                "port_scan", "Port Scan Detection",
                description="Sources probing many destination ports in a short window.",
                datasource="network_traffic",
                keywords=("portscan", "network scan", "scanning", "host scan", "reconnaissance"),
                filter="{{f.dest_port}}=*",
                pipeline="""
| bin _time span={{span}}
| stats dc({{f.dest_port}}) AS unique_ports dc({{f.dest}}) AS unique_hosts count AS attempts BY _time {{f.src}}
| where unique_ports >= {{threshold}}
| sort - unique_ports""",
                default_span="5m",
                alert=AlertSpec(threshold=100, metric="unique_ports", comparator=">=", severity=Severity.HIGH,
                                window="15m", throttle_fields=("src",)),
                correlation=True, security_domain="network", risk_object=("src", "system"), mitre=("T1046",),
            ),
        ]

    def dashboards(self):
        return [
            self.bp(
                "security_overview", "Security Operations Overview",
                description="Authentication, privilege, malware and network threat posture.",
                keywords=("security", "security overview", "soc", "security posture", "threat overview",
                          "security operations"),
                panels=(
                    PanelSpec("failed_logins", "Failed Logins", V.SINGLE),
                    PanelSpec("account_lockouts", "Account Lockouts", V.SINGLE),
                    PanelSpec("malware_detections", "Malware Detections", V.SINGLE),
                    PanelSpec("privilege_escalation", "Privileged Accounts", V.SINGLE),
                    PanelSpec("auth_failure_trend", "Authentication Failures Over Time", V.LINE),
                    PanelSpec("failed_logins", "Top Failure Sources", V.COLUMN,
                              pipeline="| stats count AS failures BY {{f.src}}\n| sort - failures\n| head 10"),
                    PanelSpec("brute_force", "Brute Force Candidates"),
                    PanelSpec("malware_detections", "Malware by Host"),
                    PanelSpec("suspicious_ip_activity", "Suspicious External IPs"),
                    PanelSpec("privilege_escalation", "Privilege Changes"),
                ),
            ),
        ]

"""PCI DSS compliance rule pack (requirement-mapped monitoring searches).

Scope searches to the cardholder data environment by overriding the ``cde_scope``
parameter in ``config/settings.yaml``::

    use_case_overrides:
      pci_failed_access:
        params: {cde_scope: 'dest_category="pci"'}
"""

from __future__ import annotations

from core.models import AlertSpec, PanelSpec, Severity, Visualization as V
from rules.base import RulePack

_CDE = {"cde_scope": ""}


class ComplianceRules(RulePack):
    domain = "compliance"
    title = "Compliance (PCI DSS)"
    description = "PCI DSS v4.0 requirement 1, 2, 5, 8 and 10 monitoring."
    domain_keywords = ("pci", "compliance", "dss", "cardholder", "cde", "regulatory")
    exclusive = True

    def use_cases(self):
        return [
            self.uc(
                "pci_failed_access", "PCI 10.2.4 - Invalid Logical Access Attempts",
                description="Failed access attempts to in-scope systems.",
                datasource="authentication",
                keywords=("pci failed access", "pci failed login", "pci invalid access", "invalid logical access",
                          "pci authentication failure", "cde failed login"),
                filter='{{p.cde_scope}} {{f.action}} IN ("failure", "failed", "fail")',
                params=_CDE,
                pipeline="""
| stats count AS failures dc({{f.user}}) AS accounts BY {{f.dest}}
| sort - failures""",
                single_value="| stats count AS failures",
                alert=AlertSpec(threshold=25, metric="failures", severity=Severity.MEDIUM, window="1h"),
                tags=("pci-10.2.4",), security_domain="access",
            ),
            self.uc(
                "pci_privileged_activity", "PCI 10.2.2 - Administrative Actions",
                description="Actions taken by accounts with root/administrative privileges.",
                datasource="windows_security",
                keywords=("pci privileged", "pci admin activity", "pci administrative action", "pci root"),
                filter="{{p.cde_scope}} {{f.event_code}} IN (4672, 4728, 4732, 4756)",
                params=_CDE,
                pipeline="""
| stats count AS events values({{f.event_code}}) AS event_codes BY {{f.user}} {{f.dest}}
| sort - events""",
                tags=("pci-10.2.2",),
            ),
            self.uc(
                "pci_audit_log_changes", "PCI 10.2.6 - Audit Log Changes",
                description="Clearing of audit logs and audit-policy changes.",
                datasource="windows_security",
                keywords=("pci audit log", "pci log tamper", "pci audit trail", "pci log cleared"),
                filter="{{p.cde_scope}} {{f.event_code}} IN (1102, 104, 4719, 4906, 4907)",
                params=_CDE,
                pipeline="""
| table _time {{f.dest}} {{f.user}} {{f.event_code}}
| sort - _time""",
                single_value="| stats count AS audit_changes",
                alert=AlertSpec(threshold=0, metric="count", severity=Severity.CRITICAL, window="15m",
                                pipeline="| stats count BY {{f.dest}} {{f.user}} {{f.event_code}}"),
                tags=("pci-10.2.6",),
            ),
            self.uc(
                "pci_account_management", "PCI 8.2 / 10.2.5 - Account Management",
                description="Creation, enablement, deletion and modification of accounts.",
                datasource="windows_security",
                keywords=("pci account change", "pci user management", "pci account management", "pci identity"),
                filter="{{p.cde_scope}} {{f.event_code}} IN (4720, 4722, 4724, 4725, 4726, 4738, 4740, 4767)",
                params=_CDE,
                pipeline="""
| eval change_type=case({{q.event_code}}=4720, "created", {{q.event_code}}=4722, "enabled", {{q.event_code}}=4724, "password reset", {{q.event_code}}=4725, "disabled", {{q.event_code}}=4726, "deleted", {{q.event_code}}=4738, "changed", {{q.event_code}}=4740, "locked out", {{q.event_code}}=4767, "unlocked")
| stats count AS changes BY change_type {{f.user}} {{f.dest}}
| sort - changes""",
                single_value="| stats count AS account_changes",
                tags=("pci-8.2", "pci-10.2.5"),
            ),
            self.uc(
                "pci_default_accounts", "PCI 2.2.2 - Vendor Default Account Usage",
                description="Successful logins with vendor-default or generic accounts.",
                datasource="authentication",
                keywords=("pci default account", "default credential", "vendor default account", "generic account"),
                filter='{{p.cde_scope}} {{f.action}}="success" {{f.user}} IN ("admin", "administrator", "root", "guest", "sa", "default", "test")',
                params=_CDE,
                pipeline="""
| stats count AS logins values({{f.src}}) AS sources BY {{f.user}} {{f.dest}}
| sort - logins""",
                alert=AlertSpec(threshold=0, metric="logins", severity=Severity.HIGH, window="1h"),
                tags=("pci-2.2.2",),
            ),
            self.uc(
                "pci_firewall_changes", "PCI 1.2 - Network Security Control Changes",
                description="Firewall / network device configuration changes.",
                datasource="network_change",
                keywords=("pci firewall change", "firewall config change", "pci network change", "firewall rule change"),
                filter='("configuration change" OR "config change" OR "%ASA-5-111008" OR "%ASA-5-111010" OR type=CONFIG)',
                pipeline="""
| stats count AS changes latest(_time) AS last_change BY {{f.host}} {{f.user}}
| convert ctime(last_change)""",
                tags=("pci-1.2",),
            ),
            self.uc(
                "pci_antivirus_detections", "PCI 5.2 - Anti-Malware Detections",
                description="Malware detections on in-scope systems.",
                datasource="endpoint",
                keywords=("pci antivirus", "pci malware", "pci anti malware"),
                filter="{{p.cde_scope}} {{f.signature}}=*",
                params=_CDE,
                pipeline="""
| stats count AS detections values({{f.signature}}) AS signatures values({{f.action}}) AS actions BY {{f.dest}}
| sort - detections""",
                single_value="| stats count AS detections",
                tags=("pci-5.2",),
            ),
        ]

    def dashboards(self):
        return [
            self.bp(
                "pci_compliance", "PCI DSS Compliance Overview",
                description="Requirement-mapped evidence for PCI DSS 1, 2, 5, 8 and 10.",
                keywords=("pci", "pci compliance", "pci dss", "compliance", "cardholder", "pci audit"),
                panels=(
                    PanelSpec("pci_failed_access", "Failed Access Attempts (10.2.4)", V.SINGLE),
                    PanelSpec("pci_audit_log_changes", "Audit Log Changes (10.2.6)", V.SINGLE),
                    PanelSpec("pci_account_management", "Account Changes (8.2)", V.SINGLE),
                    PanelSpec("pci_antivirus_detections", "Malware Detections (5.2)", V.SINGLE),
                    PanelSpec("pci_failed_access", "Failed Access Trend", V.LINE,
                              pipeline="| timechart span={{span}} count AS failures"),
                    PanelSpec("pci_account_management", "Account Changes by Event Code", V.COLUMN,
                              pipeline="| stats count AS changes BY {{f.event_code}}"),
                    PanelSpec("pci_privileged_activity", "Administrative Actions (10.2.2)"),
                    PanelSpec("pci_default_accounts", "Default Account Usage (2.2.2)"),
                    PanelSpec("pci_firewall_changes", "Network Control Changes (1.2)"),
                    PanelSpec("pci_audit_log_changes", "Audit Log Change Details"),
                    PanelSpec("pci_failed_access", "Failed Access by System"),
                ),
            ),
        ]

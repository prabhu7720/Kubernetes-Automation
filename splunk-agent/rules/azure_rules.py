"""Azure / Entra ID rule pack (Splunk Add-on for Microsoft Cloud Services / Azure)."""

from __future__ import annotations

from core.models import AlertSpec, PanelSpec, Severity, Visualization as V
from rules.base import RulePack


class AzureRules(RulePack):
    domain = "azure"
    title = "Microsoft Azure"
    description = "Entra ID sign-ins and Azure activity-log detections."
    domain_keywords = ("azure", "entra", "microsoft", "subscription", "arm", "resource group")
    exclusive = True

    def use_cases(self):
        return [
            self.uc(
                "azure_signin_failures", "Azure AD / Entra Sign-in Failures",
                description="Failed Entra ID sign-ins by user with failure reasons.",
                datasource="azure_signin",
                keywords=("azure login failure", "entra login failure", "azure fail login", "azure auth fail",
                          "login failure azure"),
                filter="{{f.result_type}}!=0",
                pipeline="""
| stats count AS failures dc({{f.src}}) AS distinct_ips values({{f.result_description}}) AS reasons BY {{f.user}}
| sort - failures
| head {{limit}}""",
                single_value="| stats count AS signin_failures",
                alert=AlertSpec(threshold=10, metric="failures", severity=Severity.MEDIUM, window="15m",
                                throttle_fields=("user",)),
                correlation=True, security_domain="access", risk_object=("user", "user"), mitre=("T1110",),
            ),
            self.uc(
                "azure_mfa_failures", "Azure MFA Failures / Fatigue",
                description="MFA required/denied result codes - possible MFA fatigue attacks.",
                datasource="azure_signin",
                keywords=("mfa failure", "mfa deny", "mfa", "mfa fatigue", "mfa push"),
                filter="{{f.result_type}} IN (50074, 50076, 50079, 500121, 50158)",
                pipeline="""
| stats count AS mfa_failures dc({{f.src}}) AS distinct_ips BY {{f.user}}
| sort - mfa_failures""",
                single_value="| stats count AS mfa_failures",
                alert=AlertSpec(threshold=5, metric="mfa_failures", severity=Severity.HIGH, window="1h",
                                throttle_fields=("user",)),
                correlation=True, security_domain="access", risk_object=("user", "user"), mitre=("T1621",),
            ),
            self.uc(
                "azure_role_assignment_changes", "Azure Role Assignment Changes",
                description="RBAC role assignment writes/deletes.",
                datasource="azure_activity",
                keywords=("role assignment", "rbac change", "azure role", "azure permission", "privileged role"),
                filter='{{f.operation}} IN ("Microsoft.Authorization/roleAssignments/write", "Microsoft.Authorization/roleAssignments/delete")',
                pipeline="""
| stats count AS changes values({{f.operation}}) AS operations latest(_time) AS last_seen BY {{f.caller}} {{f.resource_group}}
| convert ctime(last_seen)""",
                single_value="| stats count AS role_changes",
                alert=AlertSpec(threshold=0, metric="changes", severity=Severity.HIGH, window="15m"),
                correlation=True, security_domain="identity", risk_object=("caller", "user"), mitre=("T1098",),
            ),
            self.uc(
                "azure_resource_deletions", "Azure Resource Deletions",
                description="Successful delete operations per caller and resource group.",
                datasource="azure_activity",
                keywords=("resource deletion", "azure delete", "delete resource", "resource remove"),
                filter='{{f.operation}}="*/delete" {{f.activity_status}} IN ("Succeeded", "Success")',
                pipeline="""
| stats count AS deletions values({{f.operation}}) AS operations BY {{f.caller}} {{f.resource_group}}
| sort - deletions""",
                alert=AlertSpec(threshold=10, metric="deletions", severity=Severity.MEDIUM, window="1h"),
                mitre=("T1485",),
            ),
            self.uc(
                "azure_nsg_changes", "Azure NSG Changes",
                description="Network security group and rule modifications.",
                datasource="azure_activity",
                keywords=("nsg change", "network security group", "azure firewall", "azure nsg"),
                filter='{{f.operation}}="Microsoft.Network/networkSecurityGroups/*"',
                pipeline="""
| table _time {{f.caller}} {{f.operation}} {{f.resource_group}} {{f.activity_status}}
| sort - _time""",
                alert=AlertSpec(threshold=0, metric="count", severity=Severity.MEDIUM, window="15m",
                                pipeline="| stats count BY {{f.caller}} {{f.operation}}"),
                security_domain="network",
            ),
        ]

    def dashboards(self):
        return [
            self.bp(
                "azure_security", "Azure Security Overview",
                description="Entra ID sign-in health and Azure control-plane changes.",
                keywords=("azure", "azure security", "azure overview", "entra"),
                panels=(
                    PanelSpec("azure_signin_failures", "Sign-in Failures", V.SINGLE),
                    PanelSpec("azure_mfa_failures", "MFA Failures", V.SINGLE),
                    PanelSpec("azure_role_assignment_changes", "Role Changes", V.SINGLE),
                    PanelSpec("azure_signin_failures", "Sign-in Failures Over Time", V.LINE,
                              pipeline="| timechart span={{span}} count AS failures"),
                    PanelSpec("azure_signin_failures", "Top Failing Users"),
                    PanelSpec("azure_role_assignment_changes", "Role Assignment Changes"),
                    PanelSpec("azure_resource_deletions", "Resource Deletions"),
                    PanelSpec("azure_nsg_changes", "NSG Changes"),
                ),
            ),
        ]

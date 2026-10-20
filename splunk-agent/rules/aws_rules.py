"""AWS rule pack (CloudTrail via Splunk Add-on for AWS)."""

from __future__ import annotations

from core.models import AlertSpec, PanelSpec, RunbookSpec, Severity, Visualization as V
from rules.base import RulePack

_IAM_RUNBOOK = RunbookSpec(
    triage=("Who (userIdentity.arn) made the change, from which IP and region?",
            "Is there a matching change request / IaC pipeline run?"),
    investigation=("| stats count values(eventName) AS actions BY userIdentity.arn sourceIPAddress awsRegion",),
    remediation=("Revert unapproved changes (Terraform plan/apply or console).",
                 "Disable compromised access keys: aws iam update-access-key --status Inactive",
                 "Enable/verify SCP guardrails for the action."),
    escalation="Escalate to Cloud Security for any root or IAM change outside the pipeline.",
)


class AwsRules(RulePack):
    domain = "aws"
    title = "Amazon Web Services"
    description = "CloudTrail-based identity, network and logging-integrity detections."
    domain_keywords = ("aws", "amazon", "cloudtrail", "ec2", "s3", "iam", "eks", "guardduty", "cloudwatch", "vpc")
    exclusive = True

    def use_cases(self):
        return [
            self.uc(
                "aws_console_login_failures", "AWS Console Login Failures",
                description="Failed AWS console sign-ins by identity.",
                datasource="aws_cloudtrail",
                keywords=("console login failure", "aws login failure", "aws fail login", "console fail login"),
                filter="eventName=ConsoleLogin responseElements.ConsoleLogin=Failure",
                pipeline="""
| stats count AS failures values(sourceIPAddress) AS source_ips latest(errorMessage) AS reason BY userIdentity.arn
| sort - failures""",
                single_value="| stats count AS console_failures",
                alert=AlertSpec(threshold=5, metric="failures", severity=Severity.MEDIUM, window="15m"),
                correlation=True, security_domain="access", risk_object=("userIdentity.arn", "user"),
                mitre=("T1110", "T1078.004"),
            ),
            self.uc(
                "aws_unauthorized_api_calls", "AWS Unauthorized API Calls",
                description="AccessDenied / UnauthorizedOperation errors by identity.",
                datasource="aws_cloudtrail",
                keywords=("unauthorized api", "access deny", "aws access deny", "unauthorized call",
                          "permission deny", "aws deny"),
                filter='errorCode IN ("AccessDenied", "UnauthorizedOperation", "Client.UnauthorizedOperation", "AccessDeniedException")',
                pipeline="""
| stats count AS denied_calls dc(eventName) AS distinct_apis values(eventName) AS apis values(sourceIPAddress) AS source_ips BY userIdentity.arn
| sort - denied_calls
| head {{limit}}""",
                single_value="| stats count AS denied_calls",
                alert=AlertSpec(threshold=20, metric="denied_calls", severity=Severity.HIGH, window="1h"),
                correlation=True, security_domain="access", risk_object=("userIdentity.arn", "user"),
                mitre=("T1078.004",), runbook=_IAM_RUNBOOK,
            ),
            self.uc(
                "aws_root_account_usage", "AWS Root Account Usage",
                description="Any activity by the root user (should be near zero).",
                datasource="aws_cloudtrail",
                keywords=("root account", "aws root", "root login", "root usage", "root user"),
                filter="userIdentity.type=Root NOT eventType=AwsServiceEvent",
                pipeline="""
| stats count AS events values(eventName) AS actions values(sourceIPAddress) AS source_ips latest(_time) AS last_seen BY awsRegion
| convert ctime(last_seen)""",
                single_value="| stats count AS root_events",
                alert=AlertSpec(threshold=0, metric="events", severity=Severity.CRITICAL, window="15m",
                                recommended_actions=("Confirm with the account owner; root use requires break-glass approval.",
                                                     "Rotate root credentials and verify MFA if unexpected.")),
                correlation=True, security_domain="access", risk_object=("awsRegion", "other"), risk_score=80,
                mitre=("T1078.004",), runbook=_IAM_RUNBOOK,
            ),
            self.uc(
                "aws_iam_changes", "AWS IAM Changes",
                description="User, role, policy and access-key changes.",
                datasource="aws_cloudtrail",
                keywords=("iam change", "iam policy", "aws iam", "access key created", "aws policy change",
                          "aws privilege"),
                filter="eventSource=iam.amazonaws.com eventName IN (CreateUser, DeleteUser, AttachUserPolicy, DetachUserPolicy, PutUserPolicy, CreateAccessKey, AttachRolePolicy, PutRolePolicy, CreateRole, UpdateAssumeRolePolicy, AddUserToGroup, CreateLoginProfile)",
                pipeline="""
| stats count AS changes values(eventName) AS actions values(requestParameters.userName) AS target_users values(requestParameters.roleName) AS target_roles BY userIdentity.arn
| sort - changes""",
                single_value="| stats count AS iam_changes",
                alert=AlertSpec(threshold=0, metric="changes", severity=Severity.HIGH, window="1h"),
                correlation=True, security_domain="identity", risk_object=("userIdentity.arn", "user"),
                mitre=("T1098",), runbook=_IAM_RUNBOOK,
            ),
            self.uc(
                "aws_security_group_changes", "AWS Security Group Changes",
                description="Ingress/egress rule changes on security groups.",
                datasource="aws_cloudtrail",
                keywords=("security group", "sg change", "aws firewall", "ingress rule", "aws network acl"),
                filter="eventName IN (AuthorizeSecurityGroupIngress, AuthorizeSecurityGroupEgress, RevokeSecurityGroupIngress, RevokeSecurityGroupEgress, CreateSecurityGroup, DeleteSecurityGroup, ModifySecurityGroupRules)",
                pipeline="""
| table _time userIdentity.arn eventName requestParameters.groupId awsRegion sourceIPAddress
| sort - _time""",
                alert=AlertSpec(threshold=0, metric="count", severity=Severity.MEDIUM, window="15m",
                                pipeline="| stats count BY userIdentity.arn eventName requestParameters.groupId"),
                security_domain="network", mitre=("T1562.007",),
            ),
            self.uc(
                "aws_s3_policy_changes", "AWS S3 Bucket Policy / ACL Changes",
                description="Bucket policy, ACL and public-access-block changes.",
                datasource="aws_cloudtrail",
                keywords=("s3 bucket", "bucket policy", "s3 public", "s3 acl", "public bucket"),
                filter="eventSource=s3.amazonaws.com eventName IN (PutBucketPolicy, DeleteBucketPolicy, PutBucketAcl, PutBucketPublicAccessBlock, DeleteBucketPublicAccessBlock, PutBucketCors)",
                pipeline="""
| table _time userIdentity.arn eventName requestParameters.bucketName sourceIPAddress
| sort - _time""",
                alert=AlertSpec(threshold=0, metric="count", severity=Severity.HIGH, window="15m",
                                pipeline="| stats count BY userIdentity.arn eventName requestParameters.bucketName"),
                security_domain="access", mitre=("T1530",),
            ),
            self.uc(
                "aws_cloudtrail_tampering", "AWS CloudTrail Tampering",
                description="StopLogging/DeleteTrail/UpdateTrail and flow-log deletion (defense evasion).",
                datasource="aws_cloudtrail",
                keywords=("cloudtrail tamper", "stop logging", "delete trail", "cloudtrail disabled",
                          "aws logging disabled", "aws defense evasion"),
                filter="eventName IN (StopLogging, DeleteTrail, UpdateTrail, PutEventSelectors, DeleteFlowLogs)",
                pipeline="""
| stats count AS events values(eventName) AS actions latest(_time) AS last_seen BY userIdentity.arn awsRegion
| convert ctime(last_seen)""",
                alert=AlertSpec(threshold=0, metric="events", severity=Severity.CRITICAL, window="15m"),
                correlation=True, security_domain="audit", risk_object=("userIdentity.arn", "user"), risk_score=90,
                mitre=("T1562.008",),
            ),
            self.uc(
                "aws_api_error_trend", "AWS API Error Trend",
                description="CloudTrail error codes over time.",
                datasource="aws_cloudtrail",
                keywords=("aws error", "api error trend", "cloudtrail error", "aws api error"),
                filter="errorCode=*",
                pipeline="| timechart span={{span}} count BY errorCode limit={{limit}} useother=true",
                visualization=V.LINE,
            ),
            self.uc(
                "aws_ec2_changes", "AWS EC2 Instance Changes",
                description="Instance launches, stops and terminations.",
                datasource="aws_cloudtrail",
                keywords=("ec2 instance", "instance launch", "terminate instance", "ec2 change"),
                filter="eventSource=ec2.amazonaws.com eventName IN (RunInstances, TerminateInstances, StopInstances, StartInstances, ModifyInstanceAttribute)",
                pipeline="""
| stats count AS changes values(eventName) AS actions BY userIdentity.arn awsRegion
| sort - changes""",
            ),
        ]

    def dashboards(self):
        return [
            self.bp(
                "aws_security", "AWS Security & Activity",
                description="Identity, network and logging-integrity activity from CloudTrail.",
                keywords=("aws", "aws security", "cloudtrail", "aws overview", "aws activity"),
                panels=(
                    PanelSpec("aws_console_login_failures", "Console Login Failures", V.SINGLE),
                    PanelSpec("aws_unauthorized_api_calls", "Denied API Calls", V.SINGLE),
                    PanelSpec("aws_root_account_usage", "Root Account Events", V.SINGLE),
                    PanelSpec("aws_iam_changes", "IAM Changes", V.SINGLE),
                    PanelSpec("aws_api_error_trend", "API Errors Over Time"),
                    PanelSpec("aws_unauthorized_api_calls", "Top Denied APIs", V.COLUMN,
                              pipeline="| stats count AS denied BY eventName\n| sort - denied\n| head 10"),
                    PanelSpec("aws_iam_changes", "IAM Changes by Identity"),
                    PanelSpec("aws_security_group_changes", "Security Group Changes"),
                    PanelSpec("aws_s3_policy_changes", "S3 Policy Changes"),
                    PanelSpec("aws_cloudtrail_tampering", "CloudTrail Tampering"),
                ),
            ),
        ]

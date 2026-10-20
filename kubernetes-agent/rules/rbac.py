"""RBAC / IAM permission failures, missing service accounts, and agent permission gaps."""
from __future__ import annotations

import re
from typing import List

from core.k8s_utils import dig
from core.models import Scope, Severity

from ._common import impact_severity
from .base import Rule

K8S_FORBIDDEN = re.compile(
    r'User "(?P<user>[^"]+)" cannot (?P<verb>[\w-]+) resource "(?P<resource>[^"]+)"'
    r'(?: in API group "(?P<group>[^"]*)")?(?: in the namespace "(?P<ns>[^"]+)"| at the cluster scope)?', re.I)
CLOUD_IAM = r"AccessDenied|not authorized to perform|AuthorizationFailed|PERMISSION_DENIED|" \
            r"does not have .*permission|AccessDeniedException|403 Forbidden.*(amazonaws|googleapis|azure)"
GENERIC = [r"\bforbidden\b", r"\b403\b", r"Unauthorized", r"\b401\b"]
IDENTITY_ANNOTATIONS = ("eks.amazonaws.com/role-arn", "iam.gke.io/gcp-service-account", "azure.workload.identity/client-id")


class RBACPermissionRule(Rule):
    id = "K8S-RBAC-001"
    name = "RBAC / IAM permission failure"
    category = "security"
    scopes = (Scope.POD,)

    def evaluate(self, ctx):
        hits = ctx.search_logs(self.patterns("k8s", [K8S_FORBIDDEN.pattern]), max_hits=self.max_evidence)
        sa = ctx.service_account_name
        subject = f"system:serviceaccount:{ctx.namespace}:{sa}"
        if hits:
            m = K8S_FORBIDDEN.search(" ".join(h.line for h in hits))
            if m:
                verb, res = m.group("verb"), m.group("resource")
                group = m.group("group") or ""
                ns = m.group("ns")
                scope = f"namespace '{ns}'" if ns else "cluster scope"
                api_group = f'"{group}"' if group else '""'
                role_kind = "Role" if ns else "ClusterRole"
                snippet = (f"apiVersion: rbac.authorization.k8s.io/v1\nkind: {role_kind}\nmetadata:\n  name: {sa}-{res.replace('/', '-')}-{verb}\n"
                           + (f"  namespace: {ns}\n" if ns else "")
                           + f"rules:\n- apiGroups: [{api_group}]\n  resources: [\"{res}\"]\n  verbs: [\"{verb}\"]\n"
                           f"---\nkind: {role_kind}Binding  # bind to {m.group('user')}")
                return [self.finding(
                    ctx, title="RBAC permission denied", severity=impact_severity(ctx, None, Severity.HIGH, Severity.MEDIUM),
                    root_cause=f"'{m.group('user')}' is not allowed to {verb} {res} "
                               f"(API group '{group or 'core'}') at {scope}; the application calls the Kubernetes API without the "
                               "required RBAC permission.",
                    evidence=[h.render() for h in hits] + [f"Pod service account: {sa}"], confidence=95,
                    recommendations=[f"Grant the minimal permission via a {role_kind} + {role_kind}Binding to the service "
                                     f"account (example):\n{snippet}",
                                     "Confirm the pod uses the intended serviceAccountName."],
                    commands=[f"{ctx.cmd} auth can-i {verb} {res} --as={m.group('user')}" + (f" -n {ns}" if ns else ""),
                              f"{ctx.cmd} get rolebindings,clusterrolebindings -A -o wide | grep {sa}",
                              f"{ctx.cmd} describe serviceaccount {sa} -n {ctx.namespace}"])]
        cloud = ctx.search_logs(self.patterns("cloud", [CLOUD_IAM]), max_hits=self.max_evidence)
        if cloud:
            annotations = dig(ctx.service_account or {}, "metadata", "annotations") or {}
            identity = {k: v for k, v in annotations.items() if k in IDENTITY_ANNOTATIONS}
            evidence = [h.render() for h in cloud] + [f"Service account: {sa}",
                                                      f"Workload identity annotations: {identity or 'none'}"]
            root = ("The workload is denied by the cloud provider IAM (not Kubernetes RBAC): the IAM role/identity "
                    "bound to the service account lacks the permission" +
                    ("." if identity else ", and the service account has no workload-identity annotation "
                                          "(the pod falls back to the node role)."))
            return [self.finding(
                ctx, title="Cloud IAM permission denied", severity=impact_severity(ctx, None, Severity.HIGH, Severity.MEDIUM),
                root_cause=root, evidence=evidence, confidence=85 if identity else 80,
                recommendations=["Add the missing action to the IAM policy of the workload identity role.",
                                 "Annotate the service account for IRSA / GKE Workload Identity / Azure WI and restart the pods.",
                                 "Check the trust policy allows this namespace/service account."],
                commands=[f"{ctx.cmd} get sa {sa} -n {ctx.namespace} -o yaml",
                          f"{ctx.cmd} exec {ctx.name} -n {ctx.namespace} -- env | grep -Ei 'AWS_ROLE_ARN|AWS_WEB_IDENTITY|GOOGLE|AZURE'"])]
        generic = ctx.search_logs(self.patterns("generic", GENERIC), max_hits=self.max_evidence)
        token_missing = ctx.search_logs([r"/var/run/secrets/kubernetes.io/serviceaccount/token.*(no such file|not found)"],
                                        max_hits=2)
        if token_missing or (generic and ctx.spec.get("automountServiceAccountToken") is False):
            return [self.finding(
                ctx, title="Service account token not mounted", severity=Severity.HIGH,
                root_cause="The application needs the Kubernetes API but automountServiceAccountToken is disabled, "
                           "so no token is mounted and API calls are rejected.",
                evidence=[h.render() for h in token_missing + generic][: self.max_evidence] +
                         [f"automountServiceAccountToken: {ctx.spec.get('automountServiceAccountToken')}"],
                confidence=85, recommendations=["Set automountServiceAccountToken: true on the pod (or service account)."],
                commands=[f"{ctx.cmd} get pod {ctx.name} -n {ctx.namespace} -o jsonpath='{{.spec.automountServiceAccountToken}}'"])]
        if generic and len(generic) >= 2:
            return [self.finding(
                ctx, title="Authorization failures in logs", severity=Severity.MEDIUM,
                root_cause="The application logs repeated 401/403/forbidden responses from a dependency or API.",
                evidence=[h.render() for h in generic], confidence=55,
                recommendations=["Identify which API returns 401/403 and verify the credentials/permissions used."],
                commands=[f"{ctx.cmd} auth can-i --list --as={subject} -n {ctx.namespace}"])]
        return []


class ServiceAccountMissingRule(Rule):
    id = "K8S-RBAC-002"
    name = "ServiceAccount missing"
    category = "security"
    scopes = (Scope.POD,)

    def evaluate(self, ctx):
        if not ctx.service_account_checked or ctx.service_account is not None:
            return []
        sa = ctx.service_account_name
        return [self.finding(
            ctx, title="ServiceAccount missing", severity=Severity.MEDIUM,
            root_cause=f"ServiceAccount '{sa}' used by the pod no longer exists; new pods for this workload will be "
                       "rejected (error looking up service account) and token refresh will fail.",
            evidence=[f"serviceAccountName: {sa}", f"ServiceAccount {ctx.namespace}/{sa}: NOT FOUND"], confidence=92,
            recommendations=[f"Recreate the ServiceAccount: {ctx.cmd} create serviceaccount {sa} -n {ctx.namespace} "
                             "(plus its RBAC bindings / IAM annotations), or fix serviceAccountName."],
            correlation_key=f"serviceaccount:{ctx.namespace}/{sa}",
            commands=[f"{ctx.cmd} get serviceaccount {sa} -n {ctx.namespace}"])]


class AgentPermissionRule(Rule):
    """Tells the operator when the analysis is incomplete because the agent itself lacks RBAC."""

    id = "K8S-RBAC-003"
    name = "Diagnostic agent lacks permissions"
    category = "agent"
    scopes = tuple(Scope)

    def evaluate(self, ctx):
        denied = [e for e in ctx.collection_errors if "forbidden" in e.lower() or "permission denied (rbac" in e.lower()]
        if not denied:
            return []
        return [self.finding(
            ctx, title="Analysis incomplete: agent RBAC", severity=Severity.INFO,
            root_cause="The kubeconfig identity used by the agent cannot read some resources, so related rules "
                       "could not be evaluated.",
            evidence=denied[:8], confidence=100,
            recommendations=["Grant the read-only ClusterRole in deploy/rbac-readonly.yaml to the identity used by the agent."],
            commands=[f"{ctx.cmd} auth can-i --list"])]

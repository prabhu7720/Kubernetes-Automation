"""TLS / certificate problems in workloads and cert-manager Certificates."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List

from core.k8s_utils import conditions_map, dig, format_event, parse_time
from core.models import ResourceRef, Scope, Severity

from ._common import impact_severity
from .base import Rule

CERT_PATTERNS = [
    r"x509:", r"certificate verify failed", r"CERTIFICATE_VERIFY_FAILED", r"PKIX path building failed",
    r"unable to (get local issuer|verify the first) certificate", r"SSLHandshakeException",
    r"tls: (bad certificate|unknown certificate authority|handshake failure|failed to verify|expired certificate)",
    r"self[- ]signed certificate", r"certificate (has )?expired", r"ERR_TLS_CERT_ALTNAME_INVALID",
    r"doesn't match any of the subject alternative names|hostname mismatch|certificate is valid for",
    r"DEPTH_ZERO_SELF_SIGNED_CERT|UNABLE_TO_VERIFY_LEAF_SIGNATURE|CERT_HAS_EXPIRED|SELF_SIGNED_CERT_IN_CHAIN",
]

CLASSES = [
    (r"expired|not yet valid|CERT_HAS_EXPIRED",
     "A TLS certificate in the connection chain has expired (or the node/pod clock is skewed).", 90,
     ["Renew/rotate the server certificate (check cert-manager Certificate status if used).",
      "Verify NTP/clock sync on nodes if the certificate looks valid."]),
    (r"unknown authority|unable to get local issuer|PKIX|self[- ]signed|SELF_SIGNED|UNABLE_TO_VERIFY",
     "The client does not trust the CA that signed the server certificate (private/internal CA not in the trust store).", 88,
     ["Mount the internal CA bundle into the pod (e.g. trust-manager Bundle / ConfigMap) and point the runtime at it "
      "(SSL_CERT_FILE, REQUESTS_CA_BUNDLE, NODE_EXTRA_CA_CERTS, Java truststore).",
      "Never disable verification in production."]),
    (r"valid for|subject alternative names|ALTNAME|hostname mismatch",
     "The server certificate's SANs do not include the hostname the client connects to.", 90,
     ["Reissue the certificate with the correct DNS SANs, or connect using a hostname present in the certificate."]),
    (r"bad certificate|handshake failure",
     "The TLS handshake fails: mTLS client certificate rejected or protocol/cipher mismatch.", 75,
     ["Verify client certificates (mTLS) and supported TLS versions/ciphers on both sides."]),
]


class CertificateErrorRule(Rule):
    id = "K8S-CERT-001"
    name = "TLS certificate error"
    category = "security"
    scopes = (Scope.POD,)

    def evaluate(self, ctx):
        hits = ctx.search_logs(self.patterns("log", CERT_PATTERNS), max_hits=self.max_evidence)
        events = [e for e in ctx.events_matching(r"x509|certificate") if e.get("reason") not in ("Failed", "BackOff")]
        if not hits and not events:
            return []
        text = " ".join([h.line for h in hits] + [e.get("message") or "" for e in events])
        root, conf, recs = "TLS certificate validation fails (see evidence).", 70, ["Inspect the certificate chain with openssl."]
        for pattern, cause, c, r in CLASSES:
            if re.search(pattern, text, re.I):
                root, conf, recs = cause, c, list(r)
                break
        host = re.search(r"(?:https?://|connect to |for |dial tcp )([\w.-]+\.[a-z]{2,})(?::(\d+))?", text, re.I)
        target = f"{host.group(1)}:{host.group(2) or 443}" if host else "<host>:443"
        return [self.finding(
            ctx, title="TLS certificate error", severity=impact_severity(ctx, None, Severity.HIGH, Severity.MEDIUM),
            root_cause=root, evidence=[h.render() for h in hits] + [format_event(e) for e in events[-2:]],
            confidence=conf, recommendations=recs,
            commands=[f"openssl s_client -connect {target} -servername {target.split(':')[0]} -showcerts </dev/null "
                      "| openssl x509 -noout -subject -issuer -dates -ext subjectAltName",
                      f"{ctx.cmd} get certificates,certificaterequests -n {ctx.namespace}   # cert-manager",
                      f"{ctx.cmd} exec {ctx.name} -n {ctx.namespace} -- date -u"])]


class CertManagerCertificateRule(Rule):
    id = "K8S-CERT-002"
    name = "cert-manager Certificate not ready / expiring"
    category = "security"
    scopes = (Scope.NAMESPACE, Scope.CLUSTER)

    def evaluate(self, ctx):
        certs = getattr(ctx, "certificates", None)
        if not certs:
            return []
        warn_days = int(self.setting("cert_expiry_warn_days", 14))
        now = datetime.now(timezone.utc)
        findings = []
        for cert in certs:
            name, ns = dig(cert, "metadata", "name"), dig(cert, "metadata", "namespace")
            ref = ResourceRef("Certificate", name, ns)
            ready = conditions_map(cert).get("Ready") or {}
            not_after = parse_time(dig(cert, "status", "notAfter"))
            evidence = [f"Certificate {ns}/{name}: Ready={ready.get('status')} reason={ready.get('reason')}",
                        f"Message: {ready.get('message', '')}", f"notAfter: {dig(cert, 'status', 'notAfter')}",
                        f"secretName: {dig(cert, 'spec', 'secretName')}  issuer: {dig(cert, 'spec', 'issuerRef', 'name')}"]
            cmds = [f"{ctx.cmd} describe certificate {name} -n {ns}",
                    f"{ctx.cmd} get certificaterequests,orders,challenges -n {ns}",
                    f"{ctx.cmd} logs -n cert-manager deploy/cert-manager --tail=100"]
            if not_after and not_after < now:
                findings.append(self.finding(ctx, resource=ref, title="Certificate expired", severity=Severity.CRITICAL,
                                             root_cause=f"Certificate {ns}/{name} expired at {not_after.isoformat()}.",
                                             evidence=evidence, confidence=97, commands=cmds,
                                             recommendations=["Fix the issuance failure (see Ready message) and force "
                                                              "renewal: cmctl renew " + name + f" -n {ns}"]))
            elif ready.get("status") == "False":
                findings.append(self.finding(ctx, resource=ref, title="Certificate not ready", severity=Severity.HIGH,
                                             root_cause=f"cert-manager cannot issue/renew {ns}/{name}: "
                                                        f"{ready.get('message') or ready.get('reason')}",
                                             evidence=evidence, confidence=90, commands=cmds,
                                             recommendations=["Check the Issuer/ClusterIssuer status and ACME challenges "
                                                              "(DNS01/HTTP01 reachability, credentials)."]))
            elif not_after and (not_after - now).days < warn_days:
                findings.append(self.finding(ctx, resource=ref, title="Certificate expiring soon", severity=Severity.MEDIUM,
                                             root_cause=f"Certificate {ns}/{name} expires in {(not_after - now).days} day(s) "
                                                        "and has not been renewed.",
                                             evidence=evidence, confidence=85, commands=cmds,
                                             recommendations=["Verify renewal is progressing (renewBefore) and the issuer is healthy."]))
        return findings

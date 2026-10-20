"""ImagePullBackOff / ErrImagePull / InvalidImageName / ErrImageNeverPull."""
from __future__ import annotations

import re
from typing import List

from core.k8s_utils import format_event
from core.models import Finding, Scope, Severity
from core.refs import image_pull_secret_names

from ._common import describe_cmd, events_cmd, waiting
from .base import Rule

PULL_REASONS = {"ImagePullBackOff", "ErrImagePull", "InvalidImageName", "ErrImageNeverPull", "RegistryUnavailable"}

# (pattern, cause, confidence, [recommendations])
CLASSIFIERS = [
    (r"manifest unknown|manifest for .* not found|not found: manifest|repository .* not found|"
     r"name unknown|\bnot found\b.*image|failed to resolve reference.*not found",
     "The image repository or tag does not exist in the registry (typo, tag never pushed, or deleted).", 92,
     ["Verify the image name and tag exist: skopeo inspect / docker manifest inspect.",
      "Check the CI pipeline pushed the tag; prefer immutable tags or digests over 'latest'."]),
    (r"unauthorized|authentication required|pull access denied|denied:|\b401\b|\b403\b|"
     r"no basic auth credentials|requested access to the resource is denied",
     "The registry rejected the pull: authentication/authorization failed (missing, wrong or expired imagePullSecret, "
     "or node IAM role lacks pull permission).", 90,
     ["Ensure an imagePullSecret of type kubernetes.io/dockerconfigjson exists in the namespace and is referenced "
      "by the pod or its ServiceAccount.",
      "Regenerate the registry credentials if expired (ECR tokens expire after 12h; use a credential helper).",
      "For ECR/GCR/ACR, confirm the node/workload identity has pull permissions on the repository."]),
    (r"toomanyrequests|rate limit", "The registry is rate-limiting pulls (e.g. Docker Hub anonymous pull limits).", 92,
     ["Authenticate pulls with an imagePullSecret or mirror images to a private registry / pull-through cache."]),
    (r"x509|certificate signed by unknown authority|certificate has expired",
     "The node does not trust the registry's TLS certificate.", 88,
     ["Install the registry CA on the nodes (containerd certs.d / hosts.toml) or fix the registry certificate."]),
    (r"no match for platform|no matching manifest",
     "The image has no variant for the node's CPU architecture/OS.", 92,
     ["Publish a multi-arch image or schedule onto nodes matching the image architecture (kubernetes.io/arch)."]),
    (r"no space left on device", "The node ran out of disk space while pulling/unpacking the image.", 90,
     ["Free disk on the node (crictl rmi --prune), check image GC thresholds, or enlarge the node disk."]),
    (r"i/o timeout|dial tcp|no such host|connection refused|context deadline exceeded|tls handshake timeout|"
     r"network is unreachable|connection reset",
     "The node cannot reach the registry (DNS, egress firewall/security group, proxy, or registry outage).", 82,
     ["From the node, test registry reachability: crictl pull <image> / curl -v https://<registry>/v2/.",
      "Check NAT gateway / egress rules / HTTP(S)_PROXY and NO_PROXY in the container runtime config."]),
]


class ImagePullRule(Rule):
    id = "K8S-IMG-001"
    name = "Image pull failure"
    category = "image"
    scopes = (Scope.POD,)

    def evaluate(self, ctx) -> List[Finding]:
        findings = []
        for st in ctx.statuses():
            reason, message = waiting(st)
            if reason not in PULL_REASONS:
                continue
            cname = st.get("name")
            image = st.get("image") or (ctx.spec_of(cname) or {}).get("image", "?")
            events = [e for e in ctx.events_for_container(cname)
                      if e.get("reason") in ("Failed", "BackOff", "ErrImageNeverPull", "InspectFailed")]
            if not events:
                events = ctx.events_matching(re.escape(image.split("@")[0]), reasons=("Failed", "BackOff"))
            text = " ".join([message] + [e.get("message") or "" for e in events])

            evidence = [f"Container: {cname}", f"Image: {image}", f"State: Waiting ({reason})"]
            if message:
                evidence.append(f"Message: {message}")
            evidence += [format_event(e) for e in events[-3:]]

            if reason == "InvalidImageName":
                root, conf, recs = ("The image reference is syntactically invalid.", 95,
                                    ["Fix the image string (registry/repo:tag or @sha256:digest, lowercase repo)."])
            elif reason == "ErrImageNeverPull":
                root, conf, recs = ("imagePullPolicy is 'Never' but the image is not present on the node.", 95,
                                    ["Set imagePullPolicy to IfNotPresent/Always or pre-load the image on all nodes."])
            else:
                root, conf, recs = ("The kubelet cannot pull the image; the registry error is shown in the evidence.", 60,
                                    ["Inspect the pull error in the pod events and test the pull from the node."])
                for pattern, cause, c, r in CLASSIFIERS:
                    if re.search(pattern, text, re.I):
                        root, conf, recs = cause, c, list(r)
                        break

            pull_secrets = image_pull_secret_names(ctx.pod) + [
                s.get("name") for s in (ctx.service_account or {}).get("imagePullSecrets") or []]
            if pull_secrets:
                evidence.append(f"imagePullSecrets: {', '.join(pull_secrets)}")
                if ctx.secret_names is not None:
                    missing = [s for s in pull_secrets if s not in ctx.secret_names]
                    if missing:
                        evidence.append(f"imagePullSecret(s) MISSING in namespace: {', '.join(missing)}")
                        root += f" Referenced imagePullSecret(s) {', '.join(missing)} do not exist."
                        conf = max(conf, 93)
                        recs.insert(0, f"Create the missing pull secret(s): {ctx.cmd} create secret docker-registry "
                                       f"{missing[0]} -n {ctx.namespace} --docker-server=<registry> "
                                       "--docker-username=<user> --docker-password=<token>")
            else:
                evidence.append("imagePullSecrets: none (pod and service account)")
            tag = image.rsplit("/", 1)[-1]
            if "@" not in image and (":" not in tag or tag.endswith(":latest")):
                recs.append("Avoid the implicit/explicit 'latest' tag; pin a version or digest.")

            findings.append(self.finding(
                ctx, title=f"Image pull failure ({reason})", severity=Severity.HIGH, root_cause=root,
                evidence=evidence, confidence=conf, recommendations=recs, container=cname,
                commands=[describe_cmd(ctx), events_cmd(ctx),
                          f"{ctx.cmd} get pod {ctx.name} -n {ctx.namespace} -o jsonpath='{{.spec.imagePullSecrets}}'",
                          f"skopeo inspect docker://{image}   # or: docker manifest inspect {image}",
                          f"crictl pull {image}   # run on node {ctx.node_name or '<node>'}"]))
        return findings

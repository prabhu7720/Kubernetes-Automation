"""Synthetic cluster used by the test-suite and the offline demo (fake_kubectl.py).

Namespace 'payments' contains a broken deployment and several broken pods that
exercise most rules; 'kube-system' has a crash-looping CoreDNS replica; one node
has MemoryPressure and one is NotReady.
"""
from __future__ import annotations

import copy

NOW = "2026-10-20T10:00:00Z"
EARLIER = "2026-10-20T09:58:30Z"


def meta(name, ns=None, labels=None, owner=None, uid=None, **extra):
    m = {"name": name, "uid": uid or f"uid-{name}", "creationTimestamp": "2026-10-19T08:00:00Z"}
    if ns:
        m["namespace"] = ns
    if labels:
        m["labels"] = labels
    if owner:
        kind, oname = owner
        m["ownerReferences"] = [{"kind": kind, "name": oname, "uid": f"uid-{oname}", "controller": True}]
    m.update(extra)
    return m


def container(name="app", image="registry.example.com/payments/checkout:1.4.2", mem_limit="512Mi",
              mem_req="256Mi", cpu_req="100m", cpu_limit="500m", **extra):
    c = {"name": name, "image": image,
         "resources": {"requests": {"cpu": cpu_req, "memory": mem_req}, "limits": {"cpu": cpu_limit, "memory": mem_limit}},
         "ports": [{"containerPort": 8080, "name": "http"}]}
    c.update(extra)
    return c


def pod(name, ns, containers, statuses, phase="Running", node="ip-10-0-1-10", owner=None, labels=None,
        conditions=None, volumes=None, **spec_extra):
    ready = all(s.get("ready") for s in statuses) if statuses else False
    p = {"apiVersion": "v1", "kind": "Pod",
         "metadata": meta(name, ns, labels=labels or {"app": name.split("-")[0]}, owner=owner),
         "spec": {"containers": containers, "serviceAccountName": "default", "restartPolicy": "Always",
                  **({"nodeName": node} if node else {}), **({"volumes": volumes} if volumes else {}), **spec_extra},
         "status": {"phase": phase, "qosClass": "Burstable", "containerStatuses": statuses,
                    "conditions": conditions or [{"type": "PodScheduled", "status": "True"},
                                                 {"type": "Ready", "status": "True" if ready else "False"}]}}
    return p


def status(name="app", ready=False, restarts=0, waiting=None, waiting_msg="", last=None, running=False,
           image="registry.example.com/payments/checkout:1.4.2"):
    st = {"name": name, "ready": ready, "restartCount": restarts, "image": image}
    if waiting:
        st["state"] = {"waiting": {"reason": waiting, "message": waiting_msg}}
    elif running:
        st["state"] = {"running": {"startedAt": EARLIER}}
    else:
        st["state"] = {}
    st["lastState"] = {"terminated": last} if last else {}
    return st


def event(obj_kind, obj_name, ns, reason, message, etype="Warning", count=1, field_path=None):
    io = {"kind": obj_kind, "name": obj_name, "namespace": ns}
    if field_path:
        io["fieldPath"] = field_path
    return {"apiVersion": "v1", "kind": "Event", "metadata": meta(f"{obj_name}.{reason}.{count}", ns or "default"),
            "involvedObject": io, "reason": reason, "message": message, "type": etype, "count": count,
            "lastTimestamp": NOW, "firstTimestamp": EARLIER}


def node(name, ready=True, pressures=(), ready_reason="KubeletReady", ready_msg="kubelet is posting ready status"):
    conds = [{"type": t, "status": "True" if t in pressures else "False", "reason": f"Kubelet{t}" if t in pressures else "OK",
              "message": f"kubelet has {t}" if t in pressures else "", "lastTransitionTime": EARLIER}
             for t in ("MemoryPressure", "DiskPressure", "PIDPressure")]
    conds.append({"type": "Ready", "status": "True" if ready else "Unknown", "reason": ready_reason,
                  "message": ready_msg, "lastHeartbeatTime": EARLIER, "lastTransitionTime": EARLIER})
    return {"apiVersion": "v1", "kind": "Node",
            "metadata": meta(name, labels={"node.kubernetes.io/instance-type": "m6i.xlarge",
                                           "topology.kubernetes.io/zone": "us-east-1a"}),
            "spec": {"taints": [] if ready else [{"key": "node.kubernetes.io/unreachable", "effect": "NoExecute"}]},
            "status": {"conditions": conds, "allocatable": {"cpu": "3920m", "memory": "15Gi", "pods": "58"},
                       "nodeInfo": {"kubeletVersion": "v1.31.2", "containerRuntimeVersion": "containerd://1.7.22",
                                    "osImage": "Amazon Linux 2023", "architecture": "amd64"}}}


NS = "payments"
SEL = {"app": "checkout-api"}
RS = "checkout-api-768bb9ff95"

OOM_LAST = {"reason": "OOMKilled", "exitCode": 137, "startedAt": "2026-10-20T09:55:00Z", "finishedAt": "2026-10-20T09:57:40Z"}
ERR_LAST = {"reason": "Error", "exitCode": 1, "startedAt": "2026-10-20T09:59:50Z", "finishedAt": "2026-10-20T09:59:54Z"}

PODS = [
    pod(f"{RS}-abcde", NS, [container()], [status(restarts=37, waiting="CrashLoopBackOff",
        waiting_msg="back-off 5m0s restarting failed container=app", last=OOM_LAST)],
        owner=("ReplicaSet", RS), labels=SEL),
    pod(f"{RS}-fghij", NS, [container()], [status(restarts=12, waiting="CrashLoopBackOff", last=ERR_LAST)],
        owner=("ReplicaSet", RS), labels=SEL, node="ip-10-0-2-20"),
    pod(f"{RS}-klmno", NS, [container()], [status(ready=True, running=True)], owner=("ReplicaSet", RS), labels=SEL),
    pod("orders-worker-6d9f7c-x1y2z", NS,
        [container("worker", image="registry.example.com/payments/orders:2.0.1",
                   env=[{"name": "DB_PASSWORD", "valueFrom": {"secretKeyRef": {"name": "orders-db", "key": "password"}}}])],
        [status("worker", waiting="CreateContainerConfigError", waiting_msg='secret "orders-db" not found',
                image="registry.example.com/payments/orders:2.0.1")], phase="Pending"),
    pod("reporting-0", NS, [container("report", mem_req="24Gi", mem_limit="24Gi")], [], phase="Pending", node=None,
        conditions=[{"type": "PodScheduled", "status": "False", "reason": "Unschedulable",
                     "message": "0/3 nodes are available: 1 Insufficient memory, 2 node(s) had untolerated taint {dedicated: gpu}."}],
        volumes=[{"name": "data", "persistentVolumeClaim": {"claimName": "data-reporting-0"}}]),
    pod("frontend-5c8d-pq7rs", NS, [container("web", image="registry.example.com/payments/frontend:9.9.9")],
        [status("web", waiting="ImagePullBackOff", waiting_msg='Back-off pulling image "registry.example.com/payments/frontend:9.9.9"',
                image="registry.example.com/payments/frontend:9.9.9")], phase="Pending"),
    pod("api-gw-7f6b-t8u9v", NS,
        [container("gw", readinessProbe={"httpGet": {"path": "/ready", "port": 8080}, "timeoutSeconds": 1},
                   livenessProbe={"httpGet": {"path": "/healthz", "port": 9090}, "initialDelaySeconds": 5})],
        [status("gw", running=True, restarts=6, last={"reason": "Error", "exitCode": 143,
                                                        "startedAt": "2026-10-20T09:50:00Z", "finishedAt": "2026-10-20T09:51:00Z"})]),
    pod("ledger-6c5d-zz1", NS, [container("ledger")], [status("ledger", running=True, ready=False)], node="ip-10-0-3-30"),
]

KUBE_SYSTEM = [
    pod("coredns-5d78c9869d-aaaaa", "kube-system", [container("coredns", image="coredns/coredns:1.11.3")],
        [status("coredns", ready=True, running=True, image="coredns/coredns:1.11.3")], labels={"k8s-app": "kube-dns"},
        owner=("ReplicaSet", "coredns-5d78c9869d")),
    pod("coredns-5d78c9869d-bbbbb", "kube-system", [container("coredns", image="coredns/coredns:1.11.3")],
        [status("coredns", restarts=9, waiting="CrashLoopBackOff", last=ERR_LAST, image="coredns/coredns:1.11.3")],
        labels={"k8s-app": "kube-dns"}, owner=("ReplicaSet", "coredns-5d78c9869d"), node="ip-10-0-2-20"),
]

DEPLOYMENTS = [{
    "apiVersion": "apps/v1", "kind": "Deployment",
    "metadata": meta("checkout-api", NS, labels=SEL, annotations={"deployment.kubernetes.io/revision": "7"}),
    "spec": {"replicas": 3, "selector": {"matchLabels": SEL}, "strategy": {"type": "RollingUpdate",
             "rollingUpdate": {"maxSurge": "25%", "maxUnavailable": "25%"}},
             "template": {"spec": {"containers": [container()]}}},
    "status": {"replicas": 3, "updatedReplicas": 3, "readyReplicas": 1, "availableReplicas": 1, "unavailableReplicas": 2,
               "conditions": [{"type": "Available", "status": "False", "reason": "MinimumReplicasUnavailable"},
                              {"type": "Progressing", "status": "False", "reason": "ProgressDeadlineExceeded",
                               "message": f'ReplicaSet "{RS}" has timed out progressing.'}]},
}]

REPLICASETS = [
    {"apiVersion": "apps/v1", "kind": "ReplicaSet",
     "metadata": meta(RS, NS, labels=SEL, owner=("Deployment", "checkout-api"),
                      annotations={"deployment.kubernetes.io/revision": "7"}),
     "spec": {"replicas": 3, "template": {"spec": {"containers": [container()]}}}, "status": {"readyReplicas": 1}},
    {"apiVersion": "apps/v1", "kind": "ReplicaSet",
     "metadata": meta("checkout-api-5f4d8b7c6", NS, labels=SEL, owner=("Deployment", "checkout-api"),
                      annotations={"deployment.kubernetes.io/revision": "6"}),
     "spec": {"replicas": 0, "template": {"spec": {"containers": [container(image="registry.example.com/payments/checkout:1.4.1")]}}},
     "status": {}},
]

EVENTS = [
    event("Pod", f"{RS}-abcde", NS, "BackOff", "Back-off restarting failed container app", count=140,
          field_path="spec.containers{app}"),
    event("Pod", "frontend-5c8d-pq7rs", NS, "Failed",
          'Failed to pull image "registry.example.com/payments/frontend:9.9.9": rpc error: code = NotFound desc = '
          'failed to pull and unpack image: failed to resolve reference: registry.example.com/payments/frontend:9.9.9: not found',
          count=5, field_path="spec.containers{web}"),
    event("Pod", "reporting-0", NS, "FailedScheduling",
          "0/3 nodes are available: 1 Insufficient memory, 2 node(s) had untolerated taint {dedicated: gpu}. "
          "preemption: 0/3 nodes are available: 3 Preemption is not helpful for scheduling."),
    event("Pod", "api-gw-7f6b-t8u9v", NS, "Unhealthy", "Readiness probe failed: HTTP probe failed with statuscode: 503",
          count=44, field_path="spec.containers{gw}"),
    event("Pod", "api-gw-7f6b-t8u9v", NS, "Unhealthy",
          'Liveness probe failed: Get "http://10.0.1.44:9090/healthz": dial tcp 10.0.1.44:9090: connect: connection refused',
          count=18, field_path="spec.containers{gw}"),
    event("Pod", "api-gw-7f6b-t8u9v", NS, "Killing", "Container gw failed liveness probe, will be restarted",
          etype="Normal", count=6, field_path="spec.containers{gw}"),
    event("PersistentVolumeClaim", "data-reporting-0", NS, "ProvisioningFailed",
          'storageclass.storage.k8s.io "fast-ssd" not found'),
    event("Pod", "orders-worker-6d9f7c-x1y2z", NS, "Failed", 'Error: secret "orders-db" not found', count=9,
          field_path="spec.containers{worker}"),
]

NODE_EVENTS = [event("Node", "ip-10-0-3-30", "default", "NodeNotReady", "Node ip-10-0-3-30 status is now: NodeNotReady",
                     etype="Normal")]

NODES = [node("ip-10-0-1-10"), node("ip-10-0-2-20", pressures=("MemoryPressure",)),
         node("ip-10-0-3-30", ready=False, ready_reason="NodeStatusUnknown",
              ready_msg="Kubelet stopped posting node status.")]

PVCS = [{"apiVersion": "v1", "kind": "PersistentVolumeClaim", "metadata": meta("data-reporting-0", NS),
         "spec": {"storageClassName": "fast-ssd", "accessModes": ["ReadWriteOnce"],
                  "resources": {"requests": {"storage": "100Gi"}}}, "status": {"phase": "Pending"}}]

STORAGE_CLASSES = [{"apiVersion": "storage.k8s.io/v1", "kind": "StorageClass",
                    "metadata": meta("gp3", annotations={"storageclass.kubernetes.io/is-default-class": "true"}),
                    "provisioner": "ebs.csi.aws.com", "volumeBindingMode": "WaitForFirstConsumer"}]

SERVICE_ACCOUNTS = [{"apiVersion": "v1", "kind": "ServiceAccount", "metadata": meta("default", ns)}
                    for ns in (NS, "kube-system")]

NAMESPACES = [{"apiVersion": "v1", "kind": "Namespace", "metadata": meta(n), "status": {"phase": "Active"}}
              for n in (NS, "kube-system", "default")]

SECRET_NAMES = {NS: ["app-tls", "registry-creds"], "kube-system": []}
CONFIGMAP_NAMES = {NS: ["kube-root-ca.crt"], "kube-system": ["coredns"]}

LOGS = {
    f"{NS}/{RS}-abcde/app": {
        "previous": "2026-10-20T09:55:01Z INFO Starting checkout-api v1.4.2\n"
                    "2026-10-20T09:57:39Z WARN cache size 480MB\n"
                    'Exception in thread "main" java.lang.OutOfMemoryError: Java heap space\n',
        "current": ""},
    f"{NS}/{RS}-fghij/app": {
        "previous": "INFO Starting checkout-api v1.4.2\n"
                    "ERROR failed to connect to database: dial tcp 10.0.3.15:5432: connect: connection refused\n"
                    "ERROR cache init failed: dial tcp: lookup redis-master.cache.svc.cluster.local on 10.96.0.10:53: no such host\n"
                    "FATAL startup aborted password=SuperSecret123\n",
        "current": ""},
    f"{NS}/api-gw-7f6b-t8u9v/gw": {"current": "INFO listening on :8080\nWARN upstream payments unhealthy\n",
                                   "previous": "INFO listening on :8080\n"},
    "kube-system/coredns-5d78c9869d-bbbbb/coredns": {
        "previous": "[FATAL] plugin/loop: Loop (127.0.0.1:39421 -> :53) detected for zone \".\"\n", "current": ""},
}

TOP_PODS = {f"{NS}/{RS}-klmno": {"app": ("85m", "498Mi")}}
TOP_NODES = {"ip-10-0-1-10": ("1200m", "9Gi"), "ip-10-0-2-20": ("3100m", "14Gi")}


def cluster_state():
    return copy.deepcopy({
        "pods": PODS + KUBE_SYSTEM, "deployments": DEPLOYMENTS, "replicasets": REPLICASETS,
        "events": EVENTS + NODE_EVENTS, "nodes": NODES, "persistentvolumeclaims": PVCS,
        "persistentvolumes": [], "storageclasses": STORAGE_CLASSES, "serviceaccounts": SERVICE_ACCOUNTS,
        "namespaces": NAMESPACES, "resourcequotas": [], "horizontalpodautoscalers": [],
        "secrets": SECRET_NAMES, "configmaps": CONFIGMAP_NAMES, "logs": LOGS,
        "top_pods": TOP_PODS, "top_nodes": TOP_NODES,
    })

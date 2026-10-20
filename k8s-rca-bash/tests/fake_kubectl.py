#!/usr/bin/env python3
"""A tiny kubectl emulator backed by tests/fixtures/scenario.py.

Lets you run the full agent offline:
    python agent.py analyze namespace payments --kubectl tests/fake_kubectl.py
Supports exactly the read-only subset of kubectl the agent uses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures.scenario import cluster_state  # noqa: E402

ALIASES = {
    "pod": "pods", "po": "pods", "deployment": "deployments", "deploy": "deployments",
    "replicaset": "replicasets", "rs": "replicasets", "node": "nodes", "no": "nodes",
    "persistentvolumeclaim": "persistentvolumeclaims", "pvc": "persistentvolumeclaims",
    "persistentvolume": "persistentvolumes", "pv": "persistentvolumes", "storageclass": "storageclasses",
    "serviceaccount": "serviceaccounts", "sa": "serviceaccounts", "namespace": "namespaces", "ns": "namespaces",
    "event": "events", "resourcequota": "resourcequotas", "hpa": "horizontalpodautoscalers",
    "statefulset": "statefulsets", "daemonset": "daemonsets", "job": "jobs", "cronjob": "cronjobs",
}
CLUSTER_SCOPED = {"nodes", "persistentvolumes", "storageclasses", "namespaces"}
STATE = cluster_state()


def fail(msg: str, code: int = 1):
    sys.stderr.write(msg + "\n")
    sys.exit(code)


def field(obj, path):
    cur = obj
    for p in path.split("."):
        cur = cur.get(p) if isinstance(cur, dict) else None
    return cur


def match_fields(obj, selector):
    for clause in filter(None, (selector or "").split(",")):
        if "!=" in clause:
            k, v = clause.split("!=", 1)
            if str(field(obj, k)) == v:
                return False
        else:
            k, v = clause.split("=", 1)
            if str(field(obj, k)) != v:
                return False
    return True


def match_labels(obj, selector):
    labels = field(obj, "metadata.labels") or {}
    for clause in filter(None, (selector or "").split(",")):
        k, v = clause.split("=", 1)
        if labels.get(k) != v:
            return False
    return True


def parse(argv):
    opts = {"ns": None, "all": False, "l": None, "f": None, "o": None, "flags": set(), "pos": [], "tail": None}
    it = iter(argv)
    for a in it:
        if a in ("--kubeconfig", "--context", "-c"):
            v = next(it)
            if a == "-c":
                opts["container"] = v
        elif a.startswith("--request-timeout") or a.startswith("--limit-bytes") or a.startswith("--timestamps"):
            continue
        elif a.startswith("--tail="):
            opts["tail"] = int(a.split("=", 1)[1])
        elif a in ("-n", "--namespace"):
            opts["ns"] = next(it)
        elif a in ("--all-namespaces", "-A"):
            opts["all"] = True
        elif a == "-l":
            opts["l"] = next(it)
        elif a == "--field-selector":
            opts["f"] = next(it)
        elif a == "-o":
            opts["o"] = next(it)
        elif a.startswith("--"):
            opts["flags"].add(a)
        else:
            opts["pos"].append(a)
    return opts


def cmd_get(o):
    resource = o["pos"][1]
    rtype = ALIASES.get(resource, resource)
    name = o["pos"][2] if len(o["pos"]) > 2 else None
    ns = o["ns"] or "default"
    if rtype in ("secrets", "configmaps"):
        names = STATE[rtype].get(ns, [])
        print("\n".join(f"{n}   Opaque   1   1d" for n in names))
        return
    if rtype not in STATE:
        if "." in rtype or rtype in ("certificates",):
            fail(f'error: the server doesn\'t have a resource type "{resource}"')
        items = []
    else:
        items = STATE[rtype]
    if rtype not in CLUSTER_SCOPED and not o["all"]:
        items = [i for i in items if field(i, "metadata.namespace") == ns]
    items = [i for i in items if match_labels(i, o["l"]) and match_fields(i, o["f"])]
    if name:
        found = [i for i in items if field(i, "metadata.name") == name]
        if not found:
            fail(f'Error from server (NotFound): {rtype} "{name}" not found')
        print(json.dumps(found[0]))
    else:
        print(json.dumps({"apiVersion": "v1", "kind": "List", "items": items}))


def cmd_logs(o):
    pod, ns, c = o["pos"][1], o["ns"] or "default", o.get("container")
    entry = STATE["logs"].get(f"{ns}/{pod}/{c}")
    key = "previous" if "--previous" in o["flags"] else "current"
    if entry is None or entry.get(key) is None:
        if key == "previous":
            fail(f'Error from server (BadRequest): previous terminated container "{c}" in pod "{pod}" not found')
        fail(f'Error from server (BadRequest): container "{c}" in pod "{pod}" is waiting to start')
    print(entry[key], end="")


def cmd_top(o):
    if o["pos"][1] in ("pod", "pods"):
        pod, ns = o["pos"][2], o["ns"] or "default"
        usage = STATE["top_pods"].get(f"{ns}/{pod}")
        if not usage:
            fail("error: metrics not available yet")
        for c, (cpu, mem) in usage.items():
            print(f"{pod}   {c}   {cpu}   {mem}")
    else:
        for n, (cpu, mem) in STATE["top_nodes"].items():
            print(f"{n}   {cpu}   30%   {mem}   60%")


def main():
    o = parse(sys.argv[1:])
    if not o["pos"]:
        fail("usage: fake_kubectl get|logs|top|version|config")
    verb = o["pos"][0]
    if verb == "get":
        cmd_get(o)
    elif verb == "logs":
        cmd_logs(o)
    elif verb == "top":
        cmd_top(o)
    elif verb == "version":
        print(json.dumps({"serverVersion": {"gitVersion": "v1.31.2-fake"}}))
    elif verb == "config":
        print("fake-cluster")
    elif verb == "auth":
        print("yes")
    else:
        fail(f"unsupported verb {verb}")


if __name__ == "__main__":
    main()

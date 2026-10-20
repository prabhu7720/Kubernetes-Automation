#!/usr/bin/env python3
"""Builds catalog/sample_catalog.json - a realistic demo environment for offline use and tests.

    python scripts/build_sample_catalog.py && python agent.py catalog import catalog/sample_catalog.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from catalog.metadata_store import MetadataStore  # noqa: E402
from catalog.models import (METRICS_SOURCETYPE, DataModelInfo, DatasetInfo, EntityInfo, FieldInfo,  # noqa: E402
                            IndexInfo, KnowledgeObject)

NOW = time.time()

INDEXES = [("auth", "event", 4_200_000), ("wineventlog", "event", 18_000_000), ("web", "event", 52_000_000),
           ("app_logs", "event", 31_000_000), ("k8s_events", "event", 2_500_000), ("k8s_logs", "event", 90_000_000),
           ("k8s_metrics", "metric", 0), ("aws", "event", 7_000_000), ("azure", "event", 3_100_000),
           ("dns", "event", 64_000_000), ("firewall", "event", 120_000_000), ("endpoint", "event", 900_000),
           ("os", "event", 22_000_000), ("main", "event", 10_000)]

DATASETS: dict[tuple[str, str], list[str]] = {
    ("auth", "linux_secure"): ["user", "src", "action", "app", "dest", "process", "host"],
    ("wineventlog", "WinEventLog:Security"): ["EventCode", "user", "src", "dest", "action", "Account_Name",
                                             "src_user", "signature", "host", "Caller_Computer_Name"],
    ("web", "access_combined"): ["status", "uri", "clientip", "request_time", "method", "host", "bytes", "useragent"],
    ("app_logs", "_json"): ["application", "level", "status_code", "response_time", "environment", "message",
                            "host", "trace_id"],
    ("k8s_events", "kube:object:events"): ["object.reason", "object.message", "object.type",
                                           "object.involvedObject.kind", "object.involvedObject.name",
                                           "object.involvedObject.namespace", "object.source.host", "host"],
    ("k8s_logs", "kube:container:payments-api"): ["k8s.namespace.name", "k8s.pod.name", "k8s.container.name",
                                                   "k8s.node.name", "host"],
    ("k8s_logs", "kube:container:checkout"): ["k8s.namespace.name", "k8s.pod.name", "k8s.container.name",
                                               "k8s.node.name", "host"],
    ("k8s_logs", "kube:container:nginx"): ["k8s.namespace.name", "k8s.pod.name", "k8s.container.name", "host"],
    ("aws", "aws:cloudtrail"): ["eventName", "eventSource", "eventType", "errorCode", "errorMessage",
                                "sourceIPAddress", "userIdentity.arn", "userIdentity.type", "awsRegion",
                                "responseElements.ConsoleLogin", "user", "src"],
    ("azure", "azure:aad:signin"): ["properties.userPrincipalName", "properties.ipAddress", "resultType",
                                    "resultDescription", "user", "src"],
    ("azure", "azure:monitor:activity"): ["operationName.value", "caller", "resourceGroupName", "status.value"],
    ("dns", "stream:dns"): ["query", "reply_code", "src", "dest", "host"],
    ("firewall", "pan:traffic"): ["src", "dest", "dest_port", "action", "app", "user", "transport", "host"],
    ("firewall", "pan:config"): ["user", "host", "cmd", "type"],
    ("endpoint", "symantec:ep:risk:file"): ["signature", "file_name", "dest", "action", "user", "host"],
    ("os", "cpu"): ["CPU", "pctIdle", "pctUser", "pctSystem", "host"],
    ("os", "vmstat"): ["memUsedPct", "memFreeMB", "host"],
    ("os", "df"): ["UsePct", "MountedOn", "Avail", "Filesystem", "host"],
    ("os", "syslog"): ["process", "host", "message"],
}
SAMPLES = {"action": ("success", "failure"), "status": ("200", "404", "500"), "level": ("INFO", "WARN", "ERROR"),
           "object.reason": ("BackOff", "Killing", "FailedScheduling", "OOMKilling"),
           "reply_code": ("NoError", "NXDOMAIN", "SERVFAIL"), "application": ("checkout", "payments", "catalog")}
METRICS = ["container.cpu.utilization", "container.memory.usage", "k8s.container.memory_limit",
           "k8s.container.restarts", "k8s.pod.phase"]
DIMS = ["k8s.pod.name", "k8s.namespace.name", "k8s.node.name", "k8s.container.name", "k8s.cluster.name"]


def build() -> dict:
    store = MetadataStore(":memory:")
    store.replace_indexes(IndexInfo(n, t, c, round(c / 9000, 1)) for n, t, c in INDEXES)
    store.replace_datasets(DatasetInfo(i, s, 10_000 + 100 * len(f), NOW - 60) for (i, s), f in DATASETS.items())
    fields = [FieldInfo(i, s, name, 0.95, 50, SAMPLES.get(name, ()), name in ("request_time", "response_time"))
              for (i, s), names in DATASETS.items() for name in names]
    fields += [FieldInfo("k8s_metrics", METRICS_SOURCETYPE, m, 1.0, 0, (), True, "metric") for m in METRICS]
    fields += [FieldInfo("k8s_metrics", METRICS_SOURCETYPE, d, 1.0, 0, (), False, "dimension") for d in DIMS]
    store.replace_fields(fields)
    store.replace_datamodels([DataModelInfo("Authentication", "Splunk_SA_CIM", True, ("Authentication",)),
                              DataModelInfo("Web", "Splunk_SA_CIM", False, ("Web",)),
                              DataModelInfo("Network_Resolution", "Splunk_SA_CIM", True, ("DNS",)),
                              DataModelInfo("Malware", "Splunk_SA_CIM", True, ("Malware_Attacks",)),
                              DataModelInfo("Network_Traffic", "Splunk_SA_CIM", False, ("All_Traffic",))])
    kos = [
        KnowledgeObject("report", "Daily Failed Logins Summary", "search", "admin",
                        {"search": "index=auth action=failure | stats count by user", "is_scheduled": True}),
        KnowledgeObject("alert", "Excessive HTTP 5xx", "ops", "nobody", {"search": "index=web status>=500"}),
        KnowledgeObject("dashboard", "k8s_overview", "ops", "nobody", {"label": "K8s Overview", "studio": True}),
        KnowledgeObject("lookup_definition", "threat_intel_ip", "SA-ThreatIntelligence", "nobody",
                        {"type": "kvstore", "fields": ["ip", "threat_category", "threat_source"]}),
        KnowledgeObject("lookup_file", "pci_cde_assets.csv", "search", "nobody", {}),
        KnowledgeObject("kvstore", "asset_inventory", "search", "nobody", {"fields": ["host", "owner", "pci"]}),
    ]
    store.replace_knowledge_objects({k.kind for k in kos}, kos)
    store.replace_entities("host", [EntityInfo("host", h, 1000, NOW) for h in ("web01", "web02", "db01", "k8s-node-1")])
    store.replace_entities("source", [EntityInfo("source", "/var/log/secure", 5000, NOW)])
    store.set_meta("last_discovery", {"at": NOW, "ok": True, "note": "synthetic sample catalog"})
    return store.to_dict()


if __name__ == "__main__":
    out = ROOT / "catalog" / "sample_catalog.json"
    out.write_text(json.dumps(build(), indent=2), encoding="utf-8")
    print(out)

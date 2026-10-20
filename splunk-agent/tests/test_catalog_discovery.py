import tempfile
import unittest
from pathlib import Path

from tests.helpers import FakeSplunkClient, fieldsummary, make_settings, sample_store
from catalog.metadata_store import MetadataStore
from catalog.models import DatasetInfo, IndexInfo, KnowledgeObject
from discovery.engine import DiscoveryEngine
from discovery.knowledge_objects import classify_saved_search


def fake_client(fail=None):
    return FakeSplunkClient(
        rest={
            "data/indexes": [{"name": "auth", "datatype": "event", "totalEventCount": "100", "currentDBSizeMB": "5"},
                             {"name": "k8s_metrics", "datatype": "metric"},
                             {"name": "_internal", "datatype": "event"}],
            "datamodel/model": [{"name": "Authentication", "app": "Splunk_SA_CIM",
                                 "acceleration": '{"enabled": true}',
                                 "description": '{"objects": [{"objectName": "Authentication"}]}'}],
            "saved/searches": [{"name": "Nightly", "is_scheduled": "1", "alert_type": "always", "search": "index=a"},
                               {"name": "Errors alert", "alert_type": "number of events", "is_scheduled": "1"}],
            "data/ui/views": [{"name": "k8s", "isDashboard": "1", "eai:data": '<dashboard version="2">'}],
            "storage/collections/config": [{"name": "assets", "field.host": "string"}],
            "data/transforms/lookups": [{"name": "threat_intel_ip", "fields_list": "ip,threat_category"}],
            "data/lookup-table-files": [{"name": "cde.csv"}],
        },
        searches={
            "BY index sourcetype": [{"index": "auth", "sourcetype": "linux_secure", "count": "100", "last_seen": "1"}],
            "BY host": [{"host": "web01", "count": "5"}],
            "BY source": [{"source": "/var/log/secure", "count": "5"}],
            "fieldsummary": fieldsummary("host", "user", "src", "action", "date_hour", "punct"),
            "mcatalog": [{"metric_name": ["k8s.container.restarts"], "dims": ["k8s.pod.name"]}],
        },
        fail=fail)


class DiscoveryTests(unittest.TestCase):
    def test_full_discovery(self):
        store = MetadataStore(":memory:")
        report = DiscoveryEngine(fake_client(), store, make_settings().discovery).run()
        self.assertTrue(report.ok, report.to_dict())
        self.assertEqual([i.name for i in store.indexes()], ["auth", "k8s_metrics"])
        self.assertEqual(store.datasets()[0].sourcetype, "linux_secure")
        fields = store.fields("auth", "linux_secure")
        self.assertIn("user", fields)
        self.assertNotIn("date_hour", fields)
        self.assertIn("k8s.container.restarts", store.fields("k8s_metrics", "__metrics__"))
        self.assertTrue(store.datamodel("Authentication").accelerated)
        self.assertEqual({k.kind for k in store.knowledge_objects()},
                         {"report", "alert", "dashboard", "kvstore", "lookup_definition", "lookup_file"})
        self.assertEqual(store.summary()["hosts"], 1)

    def test_collector_failure_is_isolated(self):
        store = MetadataStore(":memory:")
        report = DiscoveryEngine(fake_client(fail={"datamodel/model"}), store, make_settings().discovery).run()
        self.assertFalse(report.ok)
        failed = [r.name for r in report.results if not r.ok]
        self.assertEqual(failed, ["datamodels"])
        self.assertTrue(store.indexes())

    def test_subset(self):
        client = fake_client()
        DiscoveryEngine(client, MetadataStore(":memory:"), make_settings().discovery).run(["indexes"])
        self.assertEqual(client.calls, ["data/indexes"])

    def test_classify(self):
        self.assertEqual(classify_saved_search({"is_scheduled": "1"}), "report")
        self.assertEqual(classify_saved_search({"actions": "email"}), "alert")
        self.assertEqual(classify_saved_search({}), "saved_search")


class StoreTests(unittest.TestCase):
    def test_roundtrip(self):
        store = sample_store()
        with tempfile.TemporaryDirectory() as d:
            path = store.export_json(Path(d) / "c.json")
            other = MetadataStore(str(Path(d) / "c.db"))
            other.import_json(path)
            self.assertEqual(store.summary()["fields"], other.summary()["fields"])
            self.assertEqual(len(other.knowledge_objects("lookup_definition")), 1)
            other.close()

    def test_replace_semantics(self):
        store = MetadataStore(":memory:")
        store.replace_indexes([IndexInfo("a"), IndexInfo("b")])
        store.replace_indexes([IndexInfo("c")])
        self.assertEqual([i.name for i in store.indexes()], ["c"])
        store.replace_knowledge_objects(["report"], [KnowledgeObject("report", "r1")])
        store.replace_knowledge_objects(["alert"], [KnowledgeObject("alert", "a1")])
        self.assertEqual(len(store.knowledge_objects()), 2)

    def test_wildcard_fields(self):
        store = MetadataStore(":memory:")
        store.replace_datasets([DatasetInfo("k", "kube:container:a")])
        from catalog.models import FieldInfo
        store.replace_fields([FieldInfo("k", "kube:container:a", "x", 0.5), FieldInfo("k", "kube:container:b", "y", 1)])
        self.assertEqual(set(store.fields("k", "kube:container:*")), {"x", "y"})


if __name__ == "__main__":
    unittest.main()

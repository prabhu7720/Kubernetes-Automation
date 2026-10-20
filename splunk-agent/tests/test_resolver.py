import unittest

from tests.helpers import make_settings, sample_store
from catalog.metadata_store import MetadataStore
from catalog.models import DatasetInfo, FieldInfo
from catalog.resolver import DataSourceResolver
from core.exceptions import ConfigError


def resolver(store):
    s = make_settings()
    return DataSourceResolver(store, s.datasources, s.field_aliases, s.metric_aliases)


class ResolverTests(unittest.TestCase):
    def test_catalog_selection_and_field_mapping(self):
        r = resolver(sample_store()).resolve("web", {"status_code", "uri", "src"})
        self.assertEqual(r.origin, "catalog")
        self.assertEqual(r.base, "index=web sourcetype=access_combined")
        self.assertEqual(r.field("status_code"), "status")
        self.assertEqual(r.field("src"), "clientip")

    def test_multi_dataset_union(self):
        r = resolver(sample_store()).resolve("authentication", {"user", "action"})
        self.assertEqual({d.index for d in r.datasets}, {"auth", "wineventlog"})
        self.assertTrue(r.base.startswith("((index=auth"))
        self.assertIn('sourcetype="WinEventLog:Security"', r.base)

    def test_normalization_when_aliases_differ(self):
        store = MetadataStore(":memory:")
        store.replace_datasets([DatasetInfo("auth", "linux_secure", 10), DatasetInfo("auth", "okta:im2:log", 10)])
        store.replace_fields([FieldInfo("auth", "linux_secure", "user", 1.0),
                              FieldInfo("auth", "okta:im2:log", "actor.alternateId", 1.0)])
        r = resolver(store).resolve("authentication", {"user"})
        self.assertEqual(r.field("user"), "user")
        self.assertEqual(r.normalization_eval, "eval user=coalesce(user, 'actor.alternateId')")

    def test_wildcard_sourcetype_collapse(self):
        r = resolver(sample_store()).resolve("kubernetes_logs", {"namespace", "container"})
        self.assertEqual(len(r.datasets), 1)
        self.assertEqual(r.datasets[0].sourcetype, "kube:container:*")
        self.assertEqual(r.field("namespace"), "k8s.namespace.name")

    def test_metric_resolution(self):
        r = resolver(sample_store()).resolve("kubernetes_metrics", {"pod"}, {"cpu", "restarts"})
        self.assertTrue(r.is_metric)
        self.assertEqual(r.index_clause, "index=k8s_metrics")
        self.assertEqual(r.metric("restarts"), "k8s.container.restarts")
        self.assertEqual(r.field("pod"), "k8s.pod.name")

    def test_default_fallback_on_empty_catalog(self):
        r = resolver(MetadataStore(":memory:")).resolve("kubernetes_events", {"reason", "pod"})
        self.assertEqual(r.origin, "default")
        self.assertEqual(r.base, 'index=k8s_events sourcetype="kube:object:events"')
        self.assertEqual(r.field("reason"), "object.reason")
        self.assertTrue(r.warnings)

    def test_pinned(self):
        r = resolver(sample_store()).resolve("web", {"status_code"}, pinned_indexes=["edge_web"])
        self.assertEqual((r.origin, r.base), ("pinned", "index=edge_web"))

    def test_datamodel_acceleration(self):
        self.assertTrue(resolver(sample_store()).resolve("authentication", {"user"}).datamodel_accelerated)
        self.assertFalse(resolver(sample_store()).resolve("web", {"uri"}).datamodel_accelerated)

    def test_unknown_profile(self):
        with self.assertRaises(ConfigError):
            resolver(sample_store()).resolve("nope")


if __name__ == "__main__":
    unittest.main()

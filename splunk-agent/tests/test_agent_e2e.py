import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import make_settings, sample_store, shared_agent
from core.exceptions import ConfigError, IntentResolutionError
from publishers.splunk_publisher import SplunkPublisher

EXAMPLES = [
    "Show failed login activity",
    "Create a report for top applications by errors",
    "Generate dashboard for Kubernetes health",
    "Create alert when HTTP 500 errors exceed 100 per hour",
    "Show all authentication failures from last 24 hours",
    "Create a PCI compliance dashboard",
    "Build an alert for pod restart spikes",
]


class AgentEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = shared_agent()

    def test_examples_produce_all_sections(self):
        for text in EXAMPLES:
            r = self.agent.ask(text)
            md = r.to_markdown()
            for section in ("## 1. Generated SPL", "## 2. Explanation", "## 3. Visualization Recommendation",
                            "## 4. Dashboard Component Suggestions", "## 5. Alert Recommendations",
                            "## 6. Report Definition"):
                self.assertIn(section, md, f"{text}: missing {section}")
            self.assertIn("report", r.artifacts)
            self.assertNotIn("{{", r.to_json())

    def test_write_outputs(self):
        r = self.agent.ask("Generate dashboard for Kubernetes health")
        with tempfile.TemporaryDirectory() as d:
            names = {p.name for p in r.write(d)}
            self.assertTrue({"response.md", "response.json", "search.spl"} <= names)
            self.assertTrue(any(n.startswith("dashboard_") and n.endswith(".xml") for n in names))

    def test_adhoc_fallback(self):
        r = self.agent.ask("show events from index main by host")
        self.assertEqual(r.use_cases[0].id, "adhoc_search")
        self.assertIn("index=main", r.primary_search.spl)
        self.assertIn("BY host", r.primary_search.spl)

    def test_unknown_request_gives_suggestions(self):
        with self.assertRaises(IntentResolutionError):
            self.agent.ask("bake a chocolate cake")

    def test_similar_existing_object_warning(self):
        r = self.agent.ask("Show failed logins daily summary report")
        self.assertTrue(any("Daily Failed Logins Summary" in w for w in r.warnings), r.warnings)

    def test_deploy_dry_run_and_guard(self):
        r = self.agent.ask("Create alert when HTTP 500 errors exceed 100 per hour")
        results = self.agent.deploy(r, dry_run=True)
        self.assertEqual([x.action for x in results], ["dry_run"])
        with self.assertRaises(ConfigError):
            self.agent.deploy(r, dry_run=False)


class PublisherTests(unittest.TestCase):
    def _client(self, exists: bool):
        class NotFound(Exception):
            status = 404
        service = mock.MagicMock()
        if not exists:
            service.get.side_effect = NotFound()
        return mock.MagicMock(service=service), service

    def test_create_update_skip(self):
        settings = make_settings(publish={"enabled": True}).publish
        client, service = self._client(exists=False)
        res = SplunkPublisher(client, settings).publish_saved_search("A", {"search": "index=a"}, dry_run=False)
        self.assertEqual(res.action, "created")
        service.post.assert_called_once()
        self.assertEqual(service.post.call_args.args[0], "saved/searches")

        client, service = self._client(exists=True)
        res = SplunkPublisher(client, settings).publish_saved_search("A", {"search": "index=a"}, dry_run=False)
        self.assertEqual(res.action, "skipped")

        settings = make_settings(publish={"enabled": True, "overwrite": True}).publish
        client, service = self._client(exists=True)
        res = SplunkPublisher(client, settings).publish_dashboard("dash", "<dashboard/>", dry_run=False)
        self.assertEqual(res.action, "updated")
        self.assertEqual(service.post.call_args.args[0], "data/ui/views/dash")


class ConfigTests(unittest.TestCase):
    def test_env_interpolation_and_overrides(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "settings.yaml").write_text("splunk:\n  host: ${TEST_SPLUNK_HOST:-fallback}\n  port: 8089\n")
            with mock.patch.dict("os.environ", {"TEST_SPLUNK_HOST": "splunk.prod", "SPLUNK_TOKEN": "abc"}):
                from core.config import load_settings
                s = load_settings(Path(d, "settings.yaml"))
            self.assertEqual(s.splunk.host, "splunk.prod")
            self.assertEqual(s.splunk.token, "abc")
            self.assertNotIn("abc", repr(s.splunk))

    def test_unknown_key_rejected(self):
        with self.assertRaises(ConfigError):
            make_settings(splunk={"hots": "typo"})

    def test_type_validation(self):
        with self.assertRaises(ConfigError):
            make_settings(splunk={"port": "not-a-number"})
        with self.assertRaises(ConfigError):
            make_settings(publish={"sharing": "everyone"})


if __name__ == "__main__":
    unittest.main()

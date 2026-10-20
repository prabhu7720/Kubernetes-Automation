import unittest

from tests.helpers import ROOT  # noqa: F401  (sys.path bootstrap)
from core.exceptions import IntentResolutionError
from core.intent import IntentParser
from core.models import ArtifactType, Severity
from core.nlp import normalize, stem


class NormalizeTests(unittest.TestCase):
    def test_synonyms_and_phrases(self):
        self.assertEqual(normalize("Show failed logins"), ["fail", "login"])
        self.assertEqual(normalize("authentication failures"), ["auth", "fail"])
        self.assertIn("oomkill", normalize("OOMKilled events"))
        self.assertIn("crashloop", normalize("CrashLoopBackOff pods"))
        self.assertIn("bruteforce", normalize("brute-force attack"))
        self.assertIn("privesc", normalize("privilege escalation"))

    def test_stemmer_protects_words(self):
        self.assertEqual(stem("kubernetes"), "kubernetes")
        self.assertEqual(stem("status"), "status")
        self.assertEqual(stem("restarts"), "restart")
        self.assertEqual(stem("warnings"), "warn")
        self.assertEqual(stem("pods"), "pod")


class IntentParserTests(unittest.TestCase):
    def setUp(self):
        self.p = IntentParser()

    def test_artifact_types(self):
        cases = {
            "Show failed login activity": ArtifactType.SEARCH,
            "Create a report for top applications by errors": ArtifactType.REPORT,
            "Generate dashboard for Kubernetes health": ArtifactType.DASHBOARD,
            "Build an alert for pod restart spikes": ArtifactType.ALERT,
            "Create correlation search for brute force": ArtifactType.CORRELATION,
            "Write a runbook for OOMKilled pods": ArtifactType.RUNBOOK,
            "Save this search for DNS failures as saved search": ArtifactType.SAVED_SEARCH,
            "Notify me when disk usage is above 90%": ArtifactType.ALERT,
        }
        for text, expected in cases.items():
            self.assertEqual(self.p.parse(text).artifact_type, expected, text)

    def test_threshold_window_status(self):
        i = self.p.parse("Create alert when HTTP 500 errors exceed 100 per hour")
        self.assertEqual((i.threshold, i.comparator, i.window), (100.0, ">", "1h"))
        self.assertEqual(i.status_codes, ["500"])
        self.assertNotIn("100", i.tokens)

    def test_threshold_ignores_time_units(self):
        i = self.p.parse("alert if failures over 15 minutes are more than 30")
        self.assertEqual(i.threshold, 30.0)

    def test_below_and_percent(self):
        i = self.p.parse("alert when availability drops below 99.5%")
        self.assertEqual((i.comparator, i.threshold, i.percent), ("<", 99.5, True))

    def test_time_range(self):
        i = self.p.parse("Show all authentication failures from last 24 hours")
        self.assertEqual((i.time_range.earliest, i.time_range.latest), ("-24h", "now"))
        self.assertEqual(self.p.parse("errors yesterday").time_range.earliest, "-1d@d")
        self.assertEqual(self.p.parse("failed logins in the past 7 days").time_range.earliest, "-7d")

    def test_groupby_and_top(self):
        i = self.p.parse("Create a report for top 5 applications by errors")
        self.assertEqual((i.groupby, i.limit), ("application", 5))
        self.assertEqual(self.p.parse("failed logins by source ip").groupby, "src")
        self.assertEqual(self.p.parse("Top pods by restart count").groupby, "pod")

    def test_filters(self):
        i = self.p.parse("Show failed logins for user admin index=auth status!=200")
        filters = {(f.field, f.op, f.value) for f in i.filters}
        self.assertIn(("user", "=", "admin"), filters)
        self.assertIn(("index", "=", "auth"), filters)
        self.assertIn(("status", "!=", "200"), filters)
        self.assertEqual(i.index_filters, ["auth"])
        self.assertNotIn("admin", i.tokens)

    def test_severity_schedule_title(self):
        i = self.p.parse('Create a critical severity alert for brute force daily called "BF Watch"')
        self.assertEqual(i.severity, Severity.CRITICAL)
        self.assertEqual(i.schedule, "0 6 * * *")
        self.assertEqual(i.title, "BF Watch")
        self.assertEqual(self.p.parse("p2 alert for oom").severity, Severity.HIGH)

    def test_empty(self):
        with self.assertRaises(IntentResolutionError):
            self.p.parse("   ")


if __name__ == "__main__":
    unittest.main()

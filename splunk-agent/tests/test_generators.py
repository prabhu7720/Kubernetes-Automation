import json
import unittest
import xml.etree.ElementTree as ET

from tests.helpers import empty_agent, shared_agent
from core.schedule import describe_cron, window_schedule


class SearchGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = shared_agent()

    def test_failed_logins_spl(self):
        r = self.agent.ask("Show all authentication failures from last 24 hours")
        s = r.primary_search
        self.assertIn('action IN ("failure", "failed", "fail")', s.spl)
        self.assertIn("earliest=-24h latest=now", s.adhoc_spl)
        self.assertNotIn("earliest=", s.spl)
        self.assertIn("BY user", s.spl)
        self.assertIsNotNone(s.accelerated_spl)  # Authentication DM accelerated in sample catalog
        self.assertFalse([i for i in s.lint if i.level == "error"])

    def test_groupby_override(self):
        s = self.agent.ask("failed logins by source ip").primary_search
        self.assertIn("BY src", s.spl)

    def test_user_filter_is_applied(self):
        s = self.agent.ask("failed logins for user admin").primary_search
        self.assertIn("user=admin", s.spl)

    def test_status_param(self):
        s = self.agent.ask("HTTP 503 errors").primary_search
        self.assertIn("status IN (503)", s.spl)
        s = self.agent.ask("HTTP server errors").primary_search
        self.assertIn("status IN (5*)", s.spl)

    def test_metrics_search(self):
        s = self.agent.ask("Top pods by restart count").primary_search
        self.assertTrue(s.spl.startswith("| mstats max(k8s.container.restarts)"))
        self.assertIn("index=k8s_metrics", s.spl)
        self.assertIn("BY k8s.namespace.name k8s.pod.name", s.spl)

    def test_enrichment_injected_when_lookup_exists(self):
        s = self.agent.ask("Suspicious IP activity").primary_search
        self.assertIn("| lookup threat_intel_ip ip AS src OUTPUT threat_category threat_source", s.spl)

    def test_enrichment_absent_without_lookup(self):
        s = empty_agent().ask("Suspicious IP activity").primary_search
        self.assertNotIn("lookup", s.spl)
        self.assertNotIn("{{", s.spl)

    def test_every_use_case_renders_cleanly_on_empty_catalog(self):
        agent = empty_agent()
        for uc in agent.registry.use_cases.values():
            for mode in ("search", "alert", "single"):
                s = agent.search_generator.generate(uc, None, mode=mode)
                errors = [i for i in s.lint if i.level == "error"]
                self.assertFalse(errors, f"{uc.id}/{mode}: {errors}\n{s.adhoc_spl}")


class AlertTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = shared_agent()

    def test_http_500_alert(self):
        r = self.agent.ask("Create alert when HTTP 500 errors exceed 100 per hour")
        d = r.artifact("alert").definitions[0]
        self.assertTrue(d.spl.rstrip().endswith("| where errors > 100"))
        self.assertIn("status IN (500)", d.spl)
        self.assertEqual((d.cron, d.earliest, d.latest), ("0 * * * *", "-1h@h", "@h"))
        params = d.saved_search_params()
        self.assertEqual(params["alert.severity"], "5")
        self.assertEqual(params["alert_type"], "number of events")
        self.assertIn("runbook", r.artifacts)

    def test_pod_restart_alert_defaults(self):
        d = self.agent.ask("Build an alert for pod restart spikes").artifact("alert").definitions[0]
        self.assertIn("| where restart_signals > 10", d.spl)
        self.assertEqual(d.severity.value, "high")
        self.assertEqual(d.throttle_fields, ["object.involvedObject.namespace", "object.involvedObject.name"])

    def test_threshold_in_template_not_duplicated(self):
        d = self.agent.ask("alert for brute force above 50").artifact("alert").definitions[0]
        self.assertEqual(d.spl.count("where failures"), 1)
        self.assertIn(">= 50", d.spl)

    def test_lookback_override(self):
        d = self.agent.ask("alert on hosts not reporting").artifact("alert").definitions[0]
        self.assertEqual(d.earliest, "-24h")

    def test_correlation_search(self):
        r = self.agent.ask("Create correlation search for brute force")
        cs = r.artifact("correlation")
        p = cs.saved_search_params()
        self.assertEqual(p["action.correlationsearch.enabled"], "1")
        self.assertEqual(json.loads(p["action.risk.param._risk"])[0]["risk_object_field"], "src")
        self.assertIn("T1110", p["action.correlationsearch.annotations"])

    def test_schedule_helpers(self):
        self.assertEqual(window_schedule("15m"), ("*/15 * * * *", "-15m@m", "@m"))
        self.assertEqual(window_schedule("1d"), ("15 0 * * *", "-1d@d", "@d"))
        self.assertEqual(describe_cron("0 7 * * 1"), "weekly on Monday at 07:00")


class ReportTests(unittest.TestCase):
    def test_report(self):
        r = shared_agent().ask("Create a report for top 5 applications by errors weekly")
        rpt = r.artifact("report")
        self.assertEqual(rpt.cron, "0 7 * * 1")
        self.assertEqual((rpt.earliest, rpt.latest), ("-7d@d", "@d"))
        self.assertIn("head 5", rpt.spl)
        self.assertEqual(rpt.visualization.value, "column")
        self.assertIn("[AUTO - Report - Top Applications by Error Volume]", rpt.to_conf())


class DashboardTests(unittest.TestCase):
    def _check_definition(self, d):
        for viz_id, viz in d["visualizations"].items():
            self.assertIn(viz["dataSources"]["primary"], d["dataSources"], viz_id)
            self.assertTrue(viz["type"].startswith("splunk."))
            self.assertTrue(viz["eventHandlers"])
        items = [s["item"] for s in d["layout"]["structure"]]
        self.assertEqual(sorted(items), sorted(d["visualizations"]))
        for inp in d["layout"]["globalInputs"]:
            self.assertIn(inp, d["inputs"])
        for ds in d["dataSources"].values():
            self.assertNotIn("{{", ds["options"]["query"])
        for s in d["layout"]["structure"]:
            p = s["position"]
            self.assertLessEqual(p["x"] + p["w"], 1440)

    def test_kubernetes_dashboard(self):
        r = shared_agent().ask("Generate dashboard for Kubernetes health")
        dash = r.artifact("dashboard")
        self._check_definition(dash.definition)
        kinds = {c.kind for c in dash.components}
        self.assertEqual(kinds, {"kpi", "chart", "table"})
        self.assertIn("input_namespace", dash.definition["inputs"])
        self.assertTrue(any('"$namespace$"' in ds["options"]["query"] for ds in dash.definition["dataSources"].values()))
        root = ET.fromstring(dash.to_xml())
        self.assertEqual(root.get("version"), "2")
        json.loads(root.find("definition").text)

    def test_all_blueprints_build(self):
        agent = shared_agent()
        for text in ("Create a PCI compliance dashboard", "Create a security dashboard",
                     "Generate infrastructure dashboard", "application health dashboard",
                     "aws security dashboard", "azure security dashboard"):
            self._check_definition(agent.ask(text).artifact("dashboard").definition)

    def test_auto_dashboard_without_blueprint(self):
        r = shared_agent().ask("dashboard for dns failures and firewall denies")
        self._check_definition(r.artifact("dashboard").definition)


if __name__ == "__main__":
    unittest.main()

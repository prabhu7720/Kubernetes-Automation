import unittest

from tests.helpers import shared_agent

EXPECTED = {
    "Show failed login activity": "failed_logins",
    "Show failed logins": "failed_logins",
    "Show all authentication failures from last 24 hours": "failed_logins",
    "Create a report for top applications by errors": "top_app_errors",
    "Create alert when HTTP 500 errors exceed 100 per hour": "http_status_errors",
    "Build an alert for pod restart spikes": "pod_restarts",
    "Top pods by restart count": "top_pods_restart_count",
    "HTTP 500 trends": "http_status_errors",
    "Service latency": "service_latency",
    "DNS failures": "dns_failures",
    "Container crashes": "crashloopbackoff",
    "OOMKilled events": "oomkilled",
    "Show container CPU usage": "container_cpu_usage",
    "pod memory utilization": "memory_utilization",
    "Show privilege escalation": "privilege_escalation",
    "Brute force attacks": "brute_force",
    "Suspicious IP activity": "suspicious_ip_activity",
    "Account lockouts": "account_lockouts",
    "Malware indicators": "malware_detections",
    "Node issues": "node_issues",
    "Failed scheduling": "failed_scheduling",
    "deployment failures": "deployment_failures",
    "aws root account usage": "aws_root_account_usage",
    "azure sign-in failures": "azure_signin_failures",
    "host cpu utilization": "host_cpu_utilization",
    "nginx upstream errors": "nginx_upstream_errors",
}

BLUEPRINTS = {
    "Generate dashboard for Kubernetes health": "kubernetes_health",
    "Create a PCI compliance dashboard": "pci_compliance",
    "Create a security dashboard": "security_overview",
    "Generate infrastructure dashboard": "infrastructure_health",
    "application health dashboard": "application_health",
    "aws security dashboard": "aws_security",
}


class MatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = shared_agent()

    def test_use_case_matching(self):
        for text, expected in EXPECTED.items():
            matches = self.agent.matcher.match(self.agent.parser.parse(text))
            self.assertTrue(matches, f"no match for {text!r}")
            self.assertEqual(matches[0].use_case.id, expected, f"{text!r} -> {[m.use_case.id for m in matches]}")

    def test_blueprint_matching(self):
        for text, expected in BLUEPRINTS.items():
            bps = self.agent.matcher.match_blueprints(self.agent.parser.parse(text))
            self.assertTrue(bps, text)
            self.assertEqual(bps[0].blueprint.id, expected, text)

    def test_exclusive_domains_need_mention(self):
        ids = [m.use_case.id for m in self.agent.matcher.match(self.agent.parser.parse("failed logins"))]
        self.assertFalse(any(i.startswith(("aws_", "azure_", "pci_")) for i in ids), ids)

    def test_unknown_request(self):
        self.assertEqual(self.agent.matcher.match(self.agent.parser.parse("bake a chocolate cake")), [])


if __name__ == "__main__":
    unittest.main()

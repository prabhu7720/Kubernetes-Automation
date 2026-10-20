import tempfile
import textwrap
import unittest
from pathlib import Path

from tests.helpers import make_settings, sample_store
from core.exceptions import PluginLoadError
from rules.base import RuleRegistry


class PluginTests(unittest.TestCase):
    def test_builtin_packs_loaded(self):
        reg = RuleRegistry.discover()
        self.assertTrue({"security", "kubernetes", "infrastructure", "application", "aws", "azure",
                         "compliance", "nginx"} <= set(reg.domains))
        self.assertEqual(reg.errors, [])

    def test_new_python_file_adds_capability(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "gcp_rules.py").write_text(textwrap.dedent('''
                from core.models import AlertSpec
                from rules.base import RulePack

                class GcpRules(RulePack):
                    domain = "gcp"
                    exclusive = True
                    domain_keywords = ("gcp", "google cloud")
                    datasources = {"gcp_audit": {"index_patterns": ["gcp*"], "sourcetype_patterns": ["google:gcp:pubsub:audit*"],
                                                 "default_index": "gcp", "default_sourcetype": "google:gcp:pubsub:audit:admin_activity"}}

                    def use_cases(self):
                        return [self.uc("gcp_iam_changes", "GCP IAM Changes", description="SetIamPolicy calls",
                                        datasource="gcp_audit", keywords=("gcp iam change", "setiampolicy"),
                                        filter='protoPayload.methodName="SetIamPolicy"',
                                        pipeline="| stats count BY protoPayload.authenticationInfo.principalEmail",
                                        alert=AlertSpec(threshold=0))]
            '''))
            from agent import SplunkAgent
            agent = SplunkAgent(make_settings(plugins={"rule_dirs": [d]}), store=sample_store())
            self.assertIn("gcp_iam_changes", agent.registry.use_cases)
            r = agent.ask("Show GCP IAM changes")
            self.assertEqual(r.use_cases[0].id, "gcp_iam_changes")
            self.assertIn("index=gcp", r.primary_search.spl)

    def test_yaml_pack(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "vault.yaml").write_text(textwrap.dedent('''
                domain: vault
                exclusive: true
                domain_keywords: [vault]
                use_cases:
                  - id: vault_denied
                    name: Vault Permission Denied
                    description: Denied Vault requests
                    datasource: app_logs
                    keywords: ["vault permission denied", "vault deny"]
                    filter: 'error="permission denied"'
                    pipeline: "| stats count BY {{f.user}}"
            '''))
            reg = RuleRegistry.discover([d])
            self.assertIn("vault_denied", reg.use_cases)

    def test_broken_plugin_isolated_or_strict(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "broken_rules.py").write_text("this is not python")
            reg = RuleRegistry.discover([d])
            self.assertTrue(reg.errors)
            self.assertIn("failed_logins", reg.use_cases)
            with self.assertRaises(PluginLoadError):
                RuleRegistry.discover([d], strict=True)

    def test_overrides(self):
        reg = RuleRegistry.discover(overrides={"brute_force": {"alert": {"threshold": 42}}})
        self.assertEqual(reg.use_cases["brute_force"].alert.threshold, 42)
        self.assertEqual(reg.use_cases["brute_force"].alert.metric, "failures")

    def test_custom_generator_plugin(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "jira_ticket.py").write_text(textwrap.dedent('''
                from dataclasses import dataclass
                from generators.base import Artifact, ArtifactGenerator

                @dataclass
                class Ticket(Artifact):
                    kind = "ticket"
                    title: str
                    def to_dict(self): return {"title": self.title}

                class TicketGenerator(ArtifactGenerator):
                    name = "ticket"
                    def applies(self, request): return True
                    def generate(self, request): return Ticket(title=f"Investigate {request.title}")
            '''))
            from agent import SplunkAgent
            agent = SplunkAgent(make_settings(plugins={"generator_dirs": [d]}), store=sample_store())
            self.assertEqual(agent.ask("dns failures").artifact("ticket").title, "Investigate DNS Failures")


if __name__ == "__main__":
    unittest.main()

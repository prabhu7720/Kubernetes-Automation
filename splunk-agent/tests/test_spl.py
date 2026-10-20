import unittest

from tests.helpers import ROOT  # noqa: F401
from core.exceptions import TemplateRenderError
from core.spl import lint, quote_eval_field, quote_value, split_pipes
from core.spl_explainer import explain
from core.template import render
from core.visualization import recommend
from core.models import Visualization


class SplUtilTests(unittest.TestCase):
    def test_quoting(self):
        self.assertEqual(quote_eval_field("user"), "user")
        self.assertEqual(quote_eval_field("k8s.pod.name"), "'k8s.pod.name'")
        self.assertEqual(quote_value("auth"), "auth")
        self.assertEqual(quote_value('a "b"'), '"a \\"b\\""')

    def test_split_pipes_respects_quotes_and_subsearch(self):
        stages = split_pipes('index=a "x|y" [search index=b | head 1] | stats count')
        self.assertEqual(len(stages), 2)

    def test_lint(self):
        self.assertEqual([i for i in lint("index=web | stats count by host") if i.level == "error"], [])
        codes = {i.code for i in lint('index=web "unterminated | stats count')}
        self.assertIn("unbalanced", codes)
        self.assertIn("dangerous_command", {i.code for i in lint("index=web | delete")})
        self.assertIn("no_index", {i.code for i in lint("error | stats count")})
        self.assertIn("unresolved_placeholder", {i.code for i in lint("index={{x}}")})
        self.assertIn("empty_stage", {i.code for i in lint("index=a | | stats count")})

    def test_render(self):
        self.assertEqual(render("a={{x}}", {"x": "1"}.get), "a=1")
        with self.assertRaises(TemplateRenderError):
            render("{{missing}}", {}.get)

    def test_explain(self):
        steps = explain("index=web status=500 | stats count by host | sort - count")
        self.assertIn("index web", steps[0])
        self.assertTrue(any("grouped by host" in s for s in steps))

    def test_visualization(self):
        self.assertEqual(recommend("index=a | timechart count").primary, Visualization.LINE)
        self.assertEqual(recommend("index=a | stats count").primary, Visualization.SINGLE)
        self.assertEqual(recommend("index=a | stats count by host | sort - count").primary, Visualization.COLUMN)
        self.assertEqual(recommend("index=a | stats count dc(x) by host user").primary, Visualization.TABLE)
        rec = recommend("index=a | stats count by host", Visualization.PIE)
        self.assertEqual(rec.primary, Visualization.PIE)
        self.assertIn(Visualization.COLUMN, rec.alternatives)


if __name__ == "__main__":
    unittest.main()

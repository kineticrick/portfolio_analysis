"""Integration smoke tests that run chat tools against the REAL DemoDashboardHandler
(synthetic data, no DB/network) to catch fake-vs-real data-contract drift."""
import os
os.environ.setdefault("PORTFOLIO_DEMO_MODE", "1")

import unittest

from libraries.chat import tools


class TestToolsAgainstDemoHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from visualization.dash.DemoDashboardHandler import DemoDashboardHandler
        cls.handler = DemoDashboardHandler()

    def test_get_portfolio_summary_lifetime_runs(self):
        # Lifetime always exists in the milestones; this would have caught the
        # 'Percent Return' vs 'Value % Return' column bug.
        text, fig = tools.get_portfolio_summary(self.handler, interval="Lifetime")
        self.assertIsNone(fig)
        self.assertFalse(text.startswith("Error"),
                         msg=f"tool errored against real handler: {text}")
        self.assertIn("Lifetime", text)

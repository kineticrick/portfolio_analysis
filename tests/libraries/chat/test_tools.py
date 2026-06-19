import unittest

from libraries.chat import tools
from tests.libraries.chat.fakes import make_fake_handler


class TestDataTools(unittest.TestCase):
    def setUp(self):
        self.h = make_fake_handler()

    def test_rank_assets_top_2_by_price_6m(self):
        text, fig = tools.rank_assets(self.h, interval="6m", count=2)
        self.assertIsNone(fig)
        # Highest first (descending) -> AAA and CCC both 25.0; BBB excluded.
        self.assertIn("AAA", text)
        self.assertNotIn("BBB", text)

    def test_rank_assets_filter_by_account_type(self):
        text, fig = tools.rank_assets(
            self.h, interval="6m", count=5,
            filters={"account_type": "Retirement"})
        # Only BBB is in Retirement.
        self.assertIn("BBB", text)
        self.assertNotIn("AAA", text)

    def test_get_portfolio_summary_interval(self):
        text, fig = tools.get_portfolio_summary(self.h, interval="6m")
        self.assertIsNone(fig)
        self.assertIn("3000", text.replace(",", ""))

    def test_get_asset_detail(self):
        text, fig = tools.get_asset_detail(self.h, symbol="AAA", interval="6m")
        self.assertIn("AAA", text)
        self.assertIn("Discretionary", text)

    def test_dispatch_unknown_tool_returns_error_string(self):
        text, fig = tools.dispatch(self.h, "nope", {})
        self.assertIsNone(fig)
        self.assertIn("Unknown tool", text)

    def test_dispatch_tool_error_is_caught(self):
        # Missing required 'symbol' -> dispatch returns an error string, no raise.
        text, fig = tools.dispatch(self.h, "get_asset_detail", {})
        self.assertIsNone(fig)
        self.assertTrue(text.lower().startswith("error"))

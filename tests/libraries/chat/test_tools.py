import unittest

import plotly.graph_objs as go

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
        self.assertIn("6m price return", text)

    def test_rank_assets_value_metric_uses_value_column_header(self):
        text, fig = tools.rank_assets(self.h, interval="6m", count=3,
                                      metric="value")
        self.assertIn("Value % Return", text)
        self.assertNotIn("Price % Return", text)

    def test_get_asset_detail_multi_account_lifetime_return(self):
        import pandas as pd
        h = make_fake_handler()
        # Same ticker held in two account types with different cost bases.
        h.current_portfolio_summary_df = pd.DataFrame({
            "Symbol": ["DUP", "DUP"],
            "Name": ["Dup Co", "Dup Co"],
            "Sector": ["Tech", "Tech"],
            "AssetType": ["Common Stock", "Common Stock"],
            "AccountType": ["Discretionary", "Retirement"],
            "Geography": ["US", "US"],
            "Current Price": [10.0, 10.0],
            "Current Value": [1000.0, 1000.0],
            "Cost Basis": [500.0, 1500.0],
            "Lifetime Return": [100.0, -33.33],
            "Dividend Yield": [0.0, 0.0],
            "Total Dividend": [0.0, 0.0],
        })
        text, fig = tools.get_asset_detail(h, symbol="DUP", interval="Lifetime")
        # Total value 2000 vs total cost 2000 => 0.00%, NOT the first row's 100%.
        self.assertIn("Lifetime return 0.00%", text)
        self.assertNotIn("100.00%", text)

    def test_dispatch_unknown_tool_returns_error_string(self):
        text, fig = tools.dispatch(self.h, "nope", {})
        self.assertIsNone(fig)
        self.assertIn("Unknown tool", text)

    def test_dispatch_tool_error_is_caught(self):
        # Missing required 'symbol' -> dispatch returns an error string, no raise.
        text, fig = tools.dispatch(self.h, "get_asset_detail", {})
        self.assertIsNone(fig)
        self.assertTrue(text.lower().startswith("error"))

    def test_dimension_breakdown_lifetime_uses_summary_vw(self):
        text, fig = tools.get_dimension_breakdown(
            self.h, dimension="Sector", interval="Lifetime")
        self.assertIsNone(fig)
        self.assertIn("Health", text)
        self.assertIn("25.0", text)  # Health VW Return from summary df

    def test_dimension_breakdown_window_uses_history(self):
        text, fig = tools.get_dimension_breakdown(
            self.h, dimension="Sector", interval="6m")
        # Tech grew 2400 -> 3000 over the window = 25.0%.
        self.assertIn("Tech", text)
        self.assertIn("25.0", text)

    def test_filter_holdings_returns_matches(self):
        text, fig = tools.filter_holdings(
            self.h, filters={"account_type": "Discretionary"})
        self.assertIn("AAA", text)
        self.assertIn("CCC", text)
        self.assertNotIn("BBB", text)


class TestChartTools(unittest.TestCase):
    def setUp(self):
        self.h = make_fake_handler()

    def test_show_ranked_bar_returns_figure(self):
        text, fig = tools.show_ranked_bar(self.h, interval="6m", count=3)
        self.assertIsInstance(fig, go.Figure)
        self.assertIn("AAA", text)

    def test_show_history_line_portfolio(self):
        text, fig = tools.show_history_line(
            self.h, target_type="portfolio", targets=[], interval="Lifetime")
        self.assertIsInstance(fig, go.Figure)
        self.assertGreaterEqual(len(fig.data), 1)

    def test_show_history_line_assets(self):
        text, fig = tools.show_history_line(
            self.h, target_type="asset", targets=["AAA", "BBB"],
            interval="Lifetime")
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 2)

    def test_show_history_line_dimension(self):
        text, fig = tools.show_history_line(
            self.h, target_type="dimension", targets=["Sector"],
            interval="Lifetime")
        self.assertIsInstance(fig, go.Figure)
        # Two sectors in the fake history (Tech, Health).
        self.assertEqual(len(fig.data), 2)

    def test_show_history_line_dimension_empty_targets(self):
        text, fig = tools.show_history_line(
            self.h, target_type="dimension", targets=[], interval="Lifetime")
        self.assertIsNone(fig)
        self.assertIn("targets", text)

    def test_show_history_line_dimension_unknown(self):
        text, fig = tools.show_history_line(
            self.h, target_type="dimension", targets=["Bogus"],
            interval="Lifetime")
        self.assertIsNone(fig)
        self.assertIn("Unknown dimension", text)

    def test_tool_schemas_cover_all_tools(self):
        names = {s["name"] for s in tools.TOOL_SCHEMAS}
        self.assertEqual(names, set(tools._TOOLS.keys()))
        for schema in tools.TOOL_SCHEMAS:
            self.assertIn("description", schema)
            self.assertIn("input_schema", schema)

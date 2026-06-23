import datetime
import unittest
from unittest import mock

import pandas as pd

from visualization.dash.DashboardHandler import DashboardHandler


class TestBuildByAccountExpanded(unittest.TestCase):
    def _by_account(self):
        d = datetime.date(2026, 6, 1)
        return pd.DataFrame({
            "Date": [d, d, d],
            "Symbol": ["QQQ", "QQQ", "ZZZ"],
            "AccountType": ["Discretionary", "Retirement", "Discretionary"],
            "ClosingPrice": [110.0, 110.0, 5.0],
            "Value": [1100.0, 550.0, 50.0],
        })

    def test_filters_to_portfolio_symbols_and_keeps_accounts(self):
        h = object.__new__(DashboardHandler)   # skip heavy __init__
        h.assets_history_by_account_df = self._by_account()
        with mock.patch(
                "visualization.dash.DashboardHandler.add_asset_info",
                side_effect=lambda df: df):
            out = h._build_by_account_expanded(["QQQ"])
        self.assertEqual(set(out["Symbol"]), {"QQQ"})            # ZZZ filtered out
        self.assertEqual(out["AccountType"].nunique(), 2)        # both accounts kept

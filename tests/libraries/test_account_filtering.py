import unittest
import datetime
from unittest import mock

import pandas as pd

from libraries.helpers import build_master_log
from libraries.helpers import gen_aggregated_historical_value
from libraries.helpers import compute_dimension_breakdown
from visualization.dash.DashboardHandler import DashboardHandler


class TestComputeDimensionBreakdown(unittest.TestCase):
    def _agg(self):
        return pd.DataFrame({
            "Date": [datetime.date(2026, 1, 1), datetime.date(2026, 6, 1),
                     datetime.date(2026, 1, 1), datetime.date(2026, 6, 1)],
            "Sector": ["Tech", "Tech", "Health", "Health"],
            "total_value": [2000.0, 2500.0, 400.0, 500.0],
            "total_cost_basis": [2000.0, 2000.0, 400.0, 400.0],
        })

    def test_window_uses_rebased_return(self):
        out = compute_dimension_breakdown(self._agg(), "Sector", lifetime=False)
        tech = out[out["Sector"] == "Tech"].iloc[0]
        # 2500 / 2000 - 1 = 25%
        self.assertAlmostEqual(tech["VW Return"], 25.0, places=2)
        self.assertAlmostEqual(tech["Current Value"], 2500.0, places=2)
        self.assertEqual(list(out.columns), ["Sector", "Current Value", "VW Return"])

    def test_lifetime_uses_cost_based_return(self):
        out = compute_dimension_breakdown(self._agg(), "Sector", lifetime=True)
        health = out[out["Sector"] == "Health"].iloc[0]
        # (500 - 400) / 400 = 25%
        self.assertAlmostEqual(health["VW Return"], 25.0, places=2)
        self.assertAlmostEqual(health["Current Value"], 500.0, places=2)

    def test_empty_input_returns_shaped_empty(self):
        empty = pd.DataFrame(
            columns=["Date", "Sector", "total_value", "total_cost_basis"])
        out = compute_dimension_breakdown(empty, "Sector", lifetime=False)
        self.assertTrue(out.empty)
        self.assertEqual(list(out.columns), ["Sector", "Current Value", "VW Return"])


class TestBuildMasterLogAccountFilter(unittest.TestCase):
    def test_discretionary_filter_keeps_only_discretionary_and_agnostic(self):
        log = build_master_log(account_type="Discretionary")
        self.assertFalse(log.empty)
        kinds = set(log["AccountType"].dropna().unique())
        # Only the requested account plus account-agnostic (split/acquisition) events.
        self.assertTrue(kinds.issubset({"Discretionary", "Agnostic"}),
                        f"unexpected account types: {kinds}")
        self.assertNotIn("Retirement", kinds)

    def test_no_filter_includes_both_accounts(self):
        log = build_master_log()
        kinds = set(log["AccountType"].dropna().unique())
        self.assertIn("Discretionary", kinds)
        self.assertIn("Retirement", kinds)


class TestAggregationAccountInvariant(unittest.TestCase):
    """Discretionary + Retirement must reconstitute the full portfolio exactly,
    per (Date, Sector). Proves the account filter neither drops nor double-counts."""

    def test_account_split_sums_to_full(self):
        start = "2026-01-01"
        full = gen_aggregated_historical_value("Sector", start_date=start)
        disc = gen_aggregated_historical_value(
            "Sector", start_date=start, account_type="Discretionary")
        ret = gen_aggregated_historical_value(
            "Sector", start_date=start, account_type="Retirement")

        split = (pd.concat([disc, ret])
                 .groupby(["Date", "Sector"], as_index=False)["total_value"].sum())
        merged = full.merge(split, on=["Date", "Sector"], how="outer",
                            suffixes=("_full", "_split")).fillna(0.0)
        diff = (merged["total_value_full"] - merged["total_value_split"]).abs()
        self.assertTrue((diff < 0.01).all(),
                        f"mismatched rows:\n{merged[diff >= 0.01]}")


class TestHandlerFilteredSeam(unittest.TestCase):
    def test_forwards_args_and_returns_aggregated_df(self):
        sentinel = pd.DataFrame({"Date": [datetime.date(2026, 1, 1)],
                                 "Sector": ["Tech"], "total_value": [1.0],
                                 "total_cost_basis": [1.0]})
        # Build an instance without running the heavy __init__.
        handler = object.__new__(DashboardHandler)
        with mock.patch(
                "visualization.dash.DashboardHandler.gen_aggregated_historical_value",
                return_value=sentinel) as agg:
            out = handler.get_filtered_dimension_history(
                "Sector", account_type="Discretionary",
                symbols=["AAA"], start_date="2026-01-01")
        agg.assert_called_once_with("Sector", symbols=["AAA"],
                                    start_date="2026-01-01",
                                    account_type="Discretionary")
        self.assertIs(out, sentinel)

    def test_symbols_none_becomes_empty_list(self):
        sentinel = pd.DataFrame()
        handler = object.__new__(DashboardHandler)
        with mock.patch(
                "visualization.dash.DashboardHandler.gen_aggregated_historical_value",
                return_value=sentinel) as agg:
            handler.get_filtered_dimension_history("Sector")
        agg.assert_called_once_with("Sector", symbols=[], start_date=None,
                                    account_type=None)


class TestAccountLabelCleaning(unittest.TestCase):
    def test_value_rows_have_clean_account_labels(self):
        from libraries.helpers import gen_assets_historical_value
        df = gen_assets_historical_value(cadence="daily", start_date="2026-01-01")
        self.assertIn("AccountType", df.columns)
        labels = set(df["AccountType"].unique())
        self.assertTrue(labels.issubset({"Discretionary", "Retirement"}),
                        f"leaked labels present: {labels}")

    def test_account_dimension_has_no_agnostic_bucket(self):
        from libraries.helpers import gen_aggregated_historical_value
        agg = gen_aggregated_historical_value("AccountType", start_date="2026-01-01")
        self.assertNotIn("Agnostic", set(agg["AccountType"].unique()))

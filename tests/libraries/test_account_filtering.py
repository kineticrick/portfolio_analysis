import unittest

import pandas as pd

from libraries.helpers import build_master_log
from libraries.helpers import gen_aggregated_historical_value


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

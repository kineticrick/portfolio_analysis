import unittest

import pandas as pd

from libraries.helpers import build_master_log


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

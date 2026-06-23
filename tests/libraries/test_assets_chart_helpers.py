import datetime
import unittest

import pandas as pd

from visualization.dash.assets_chart_helpers import prepare_per_account_chart_df


def _expanded():
    old = datetime.date(2026, 1, 1)
    mid = datetime.date(2026, 6, 1)
    rows = [
        (old, "QQQ", "Discretionary", 100.0, 1000.0),
        (mid, "QQQ", "Discretionary", 110.0, 1100.0),
        (old, "QQQ", "Retirement", 100.0, 500.0),
        (mid, "QQQ", "Retirement", 110.0, 550.0),
        (old, "AAA", "Discretionary", 50.0, 500.0),
        (mid, "AAA", "Discretionary", 60.0, 600.0),
    ]
    return pd.DataFrame(rows, columns=["Date", "Symbol", "AccountType",
                                       "ClosingPrice", "Value"])


def _summary():
    return pd.DataFrame({
        "Symbol": ["QQQ", "QQQ", "AAA"],
        "AccountType": ["Discretionary", "Retirement", "Discretionary"],
        "Current Price": [120.0, 120.0, 65.0],
        "Current Value": [1200.0, 600.0, 650.0],
    })


_MILESTONES = [("1d", 1), ("1m", 30), ("6m", 180), ("1y", 365)]


class TestPreparePerAccountChartDf(unittest.TestCase):
    def test_all_pairs_when_no_selection(self):
        out = prepare_per_account_chart_df(
            _expanded(), _summary(), None, "Lifetime", _MILESTONES)
        pairs = set(map(tuple, out[["Symbol", "AccountType"]].drop_duplicates()
                        .to_records(index=False)))
        self.assertEqual(
            pairs,
            {("QQQ", "Discretionary"), ("QQQ", "Retirement"),
             ("AAA", "Discretionary")})

    def test_selected_pairs_filter(self):
        out = prepare_per_account_chart_df(
            _expanded(), _summary(), {("QQQ", "Retirement")}, "Lifetime",
            _MILESTONES)
        self.assertEqual(set(out["Symbol"]), {"QQQ"})
        self.assertEqual(set(out["AccountType"]), {"Retirement"})

    def test_rebase_per_account_starts_at_zero(self):
        out = prepare_per_account_chart_df(
            _expanded(), _summary(), None, "Lifetime", _MILESTONES)
        for _, g in out.groupby(["Symbol", "AccountType"]):
            g = g.sort_values("Date")
            self.assertAlmostEqual(g["ClosingPrice % Change"].iloc[0], 0.0)

    def test_today_point_uses_per_account_summary(self):
        out = prepare_per_account_chart_df(
            _expanded(), _summary(), {("QQQ", "Retirement")}, "Lifetime",
            _MILESTONES)
        today = pd.Timestamp("today").normalize()
        last = out[out["Date"] == today]
        self.assertEqual(len(last), 1)
        self.assertAlmostEqual(float(last["ClosingPrice"].iloc[0]), 120.0)
        # 120 / 100 - 1 = 20%
        self.assertAlmostEqual(float(last["ClosingPrice % Change"].iloc[0]), 20.0)

    def test_interval_window_drops_old_dates(self):
        full = prepare_per_account_chart_df(
            _expanded(), _summary(), {("AAA", "Discretionary")}, "Lifetime",
            _MILESTONES)
        windowed = prepare_per_account_chart_df(
            _expanded(), _summary(), {("AAA", "Discretionary")}, "1d",
            _MILESTONES)
        self.assertLess(len(windowed), len(full))

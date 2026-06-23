import datetime
import unittest

import pandas as pd

from libraries.db import sql
from libraries.helpers import aggregate_assets_history_by_symbol


class TestAssetsHistorySchema(unittest.TestCase):
    def test_create_sql_has_account_type_in_pk(self):
        create = sql.create_assets_history_table_sql
        self.assertIn("account_type", create)
        self.assertIn("PRIMARY KEY (date, symbol, account_type)", create)

    def test_read_columns_match_table_column_order(self):
        # Column names in the CREATE statement must map 1:1 (and in order) to
        # read_assets_history_columns, because mysql_to_df assigns column names
        # positionally to `SELECT *`. Match each column name that precedes a
        # type keyword — parens-aware, so DECIMAL(13, 2)'s inner comma is ignored
        # and the PRIMARY KEY clause (no type keyword) is skipped.
        import re
        create = sql.create_assets_history_table_sql
        col_names = re.findall(r"(\w+)\s+(?:DATE|VARCHAR|INT|DECIMAL)", create)
        mapping = {
            "date": "Date", "symbol": "Symbol", "account_type": "AccountType",
            "quantity": "Quantity", "cost_basis": "CostBasis",
            "closing_price": "ClosingPrice", "value": "Value",
            "percent_return": "PercentReturn",
        }
        expected = [mapping[c] for c in col_names]
        self.assertEqual(expected, sql.read_assets_history_columns)


class TestAggregateBySymbol(unittest.TestCase):
    def _per_account(self):
        d = datetime.date(2026, 1, 2)
        return pd.DataFrame({
            "Date": [d, d, d],
            "Symbol": ["DUP", "DUP", "SOLO"],
            "AccountType": ["Discretionary", "Retirement", "Discretionary"],
            "Quantity": [10, 5, 3],
            "CostBasis": [100.0, 60.0, 30.0],
            "ClosingPrice": [12.0, 12.0, 8.0],
            "Value": [120.0, 60.0, 24.0],
            "PercentReturn": [20.0, 0.0, -20.0],
        })

    def test_multi_account_symbol_collapses_to_one_row(self):
        out = aggregate_assets_history_by_symbol(self._per_account())
        dup = out[out["Symbol"] == "DUP"]
        self.assertEqual(len(dup), 1)
        row = dup.iloc[0]
        self.assertEqual(row["Quantity"], 15)          # 10 + 5
        self.assertAlmostEqual(row["CostBasis"], 160.0)  # 100 + 60
        self.assertAlmostEqual(row["Value"], 180.0)      # 120 + 60
        self.assertAlmostEqual(row["ClosingPrice"], 12.0)  # identical, 'first'
        # return recomputed from summed totals: (180 - 160) / 160 * 100 = 12.5
        self.assertAlmostEqual(row["PercentReturn"], 12.5)
        self.assertNotIn("AccountType", out.columns)

    def test_single_account_symbol_unchanged(self):
        out = aggregate_assets_history_by_symbol(self._per_account())
        solo = out[out["Symbol"] == "SOLO"].iloc[0]
        self.assertEqual(solo["Quantity"], 3)
        self.assertAlmostEqual(solo["Value"], 24.0)

    def test_idempotent_on_per_symbol_frame(self):
        once = aggregate_assets_history_by_symbol(self._per_account())
        twice = aggregate_assets_history_by_symbol(once)
        self.assertEqual(len(once), len(twice))

    def test_zero_cost_basis_guarded(self):
        d = datetime.date(2026, 1, 2)
        df = pd.DataFrame({
            "Date": [d], "Symbol": ["Z"], "AccountType": ["Discretionary"],
            "Quantity": [1], "CostBasis": [0.0], "ClosingPrice": [5.0],
            "Value": [5.0], "PercentReturn": [0.0]})
        out = aggregate_assets_history_by_symbol(df)
        self.assertEqual(out.iloc[0]["PercentReturn"], 0.0)


from libraries.HistoryHandlers.AssetHistoryHandler import build_assets_history_rows


class TestBuildAssetsHistoryRows(unittest.TestCase):
    def test_one_tuple_per_row_with_account_type(self):
        d = datetime.date(2026, 1, 2)
        df = pd.DataFrame({
            "Date": [d, d],
            "Symbol": ["DUP", "DUP"],
            "AccountType": ["Discretionary", "Retirement"],
            "Quantity": [10, 5],
            "CostBasis": [100.0, 60.0],
            "ClosingPrice": [12.0, 12.0],
            "Value": [120.0, 60.0],
            "PercentReturn": [20.0, 0.0],
        })
        rows = build_assets_history_rows(df)
        self.assertEqual(len(rows), 2)            # both accounts preserved
        self.assertTrue(all(len(t) == 8 for t in rows))
        self.assertEqual({t[2] for t in rows}, {"Discretionary", "Retirement"})
        # field order: (Date, Symbol, AccountType, Quantity, CostBasis,
        #               ClosingPrice, Value, PercentReturn)
        self.assertEqual(rows[0][1], "DUP")

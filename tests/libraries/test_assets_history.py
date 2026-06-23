import unittest

from libraries.db import sql


class TestAssetsHistorySchema(unittest.TestCase):
    def test_create_sql_has_account_type_in_pk(self):
        create = sql.create_assets_history_table_sql
        self.assertIn("account_type", create)
        self.assertIn("PRIMARY KEY (date, symbol, account_type)", create)

    def test_read_columns_match_table_column_order(self):
        # Column names in the CREATE statement, before PRIMARY KEY, must map
        # 1:1 (and in order) to read_assets_history_columns, because mysql_to_df
        # assigns column names positionally to `SELECT *`.
        create = sql.create_assets_history_table_sql
        body = create[create.index("(") + 1: create.index("PRIMARY KEY")]
        col_names = [seg.strip().split()[0] for seg in body.split(",")
                     if seg.strip()]
        mapping = {
            "date": "Date", "symbol": "Symbol", "account_type": "AccountType",
            "quantity": "Quantity", "cost_basis": "CostBasis",
            "closing_price": "ClosingPrice", "value": "Value",
            "percent_return": "PercentReturn",
        }
        expected = [mapping[c] for c in col_names]
        self.assertEqual(expected, sql.read_assets_history_columns)

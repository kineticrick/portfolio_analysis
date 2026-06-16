import unittest
import pandas as pd
from libraries.returns import value_weighted_lifetime_return, rebase_to_window_start


class TestReturns(unittest.TestCase):
    def test_value_weighted_lifetime_return_biotech(self):
        # Real Biotech holdings on 2026-06-14: LLY + FATE
        total_value = pd.Series([27192.0 + 1809.0])
        total_cost_basis = pd.Series([13337.0 + 2602.0])
        result = value_weighted_lifetime_return(total_value, total_cost_basis)
        self.assertAlmostEqual(result.iloc[0], 81.95, places=1)

    def test_rebase_is_multiplicative_not_subtractive(self):
        # 3.25x -> 3.75x growth multiple over the window = 15.4%, not 50 "points"
        values = pd.Series([325.0, 375.0])
        result = rebase_to_window_start(values)
        self.assertAlmostEqual(result.iloc[0], 0.0, places=6)      # starts at 0%
        self.assertAlmostEqual(result.iloc[1], 15.3846, places=3)  # 375/325 - 1

    def test_rebase_first_point_is_zero(self):
        values = pd.Series([100.0, 110.0, 90.0])
        result = rebase_to_window_start(values)
        self.assertEqual(result.iloc[0], 0.0)
        self.assertAlmostEqual(result.iloc[2], -10.0, places=6)


if __name__ == '__main__':
    unittest.main()

import unittest
import pandas as pd
import plotly.graph_objs as go

from libraries.chat.chart_builders import build_history_line, build_ranked_bar


class TestChartBuilders(unittest.TestCase):
    def test_history_line_rebases_each_series_to_zero(self):
        df = pd.DataFrame({
            "Date": pd.to_datetime(["2026-01-01", "2026-01-02",
                                    "2026-01-01", "2026-01-02"]),
            "Label": ["AAA", "AAA", "BBB", "BBB"],
            "Value": [100.0, 110.0, 200.0, 180.0],
        })
        fig = build_history_line(df, label_col="Label", value_col="Value",
                                 title="t")
        self.assertIsInstance(fig, go.Figure)
        # Two series, each starting at 0%.
        self.assertEqual(len(fig.data), 2)
        for trace in fig.data:
            self.assertAlmostEqual(trace.y[0], 0.0, places=6)

    def test_ranked_bar_has_one_bar_per_row(self):
        df = pd.DataFrame({"Symbol": ["AAA", "BBB", "CCC"],
                           "Return": [12.5, 8.0, -3.0]})
        fig = build_ranked_bar(df, label_col="Symbol", value_col="Return",
                               title="Top movers")
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 1)
        self.assertEqual(list(fig.data[0].x), ["AAA", "BBB", "CCC"])
        self.assertEqual(list(fig.data[0].y), [12.5, 8.0, -3.0])

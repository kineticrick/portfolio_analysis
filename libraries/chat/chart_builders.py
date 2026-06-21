"""Pure plotly figure builders for the chat tab. DataFrame in, Figure out."""

import plotly.express as px
import plotly.graph_objs as go

from libraries.returns import rebase_to_window_start


def build_history_line(df, label_col, value_col, title):
    """Rebased % line chart: each series (grouped by label_col) starts at 0%.

    df must have columns: 'Date', label_col, value_col.
    """
    df = df.sort_values([label_col, "Date"]).copy()
    df["pct"] = df.groupby(label_col)[value_col].transform(rebase_to_window_start)
    fig = px.line(df, x="Date", y="pct", color=label_col, title=title)
    fig.update_yaxes(ticksuffix="%")
    fig.update_layout(height=500)
    return fig


def build_ranked_bar(df, label_col, value_col, title):
    """Simple bar chart, one bar per row, in the order given."""
    fig = go.Figure(go.Bar(x=list(df[label_col]), y=list(df[value_col])))
    fig.update_layout(title=title, height=500)
    fig.update_yaxes(ticksuffix="%")
    return fig

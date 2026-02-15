from dash import callback, dcc, Input, Output, html
import dash_ag_grid as dag
import plotly.express as px
import pandas as pd
from pandas.tseries.offsets import DateOffset

from visualization.dash.portfolio_dashboard.globals import *
import dash_bootstrap_components as dbc


def create_dimension_tab(dimension_name, column_name, summary_df_attr, history_df_attr):
    """Factory function to create a dimension tab (sectors, asset_types, etc.)

    Args:
        dimension_name: Tab identifier used in component IDs (e.g. "sectors")
        column_name: DataFrame column name for the dimension (e.g. "Sector")
        summary_df_attr: Attribute name on DASH_HANDLER for summary DataFrame
        history_df_attr: Attribute name on DASH_HANDLER for history DataFrame

    Returns:
        dbc.Container layout for the tab
    """
    # Get summary data
    summary_df = getattr(DASH_HANDLER, summary_df_attr)

    # Build ag-grid column definitions from the DataFrame columns
    column_defs = [{"field": col, "sortable": True, "filter": True,
                    "checkboxSelection": (col == column_name),
                    "headerCheckboxSelection": (col == column_name)}
                   for col in summary_df.columns]

    # Register the graph update callback
    @callback(
        Output(f'{dimension_name}-history-graph', 'figure'),
        Input(f'{dimension_name}-table', 'selectedRows'),
        Input(f'{dimension_name}-interval-dropdown', 'value'))
    def update_hist_graph(selected_rows, interval):
        history_df = getattr(DASH_HANDLER, history_df_attr)

        # Filter by selected rows
        if selected_rows:
            selected_values = [row[column_name] for row in selected_rows]
            history_df = history_df[history_df[column_name].isin(selected_values)]

        # Filter by interval
        if interval != "Lifetime":
            interval_days = {k: v for (k, v) in DASH_HANDLER.performance_milestones}
            days = interval_days[interval]
            offset = DateOffset(days=days)
            start_date = (pd.to_datetime('today') - offset).date()
            history_df = history_df[history_df['Date'] >= start_date]

        fig = px.line(
            history_df,
            x=history_df['Date'],
            y=history_df['AvgPercentReturn'],
            hover_data={'AvgPercentReturn': ':.2f%'},
            color=history_df[column_name],
        )
        fig.update_layout(height=800)
        fig.update_yaxes(ticksuffix="%")

        return fig

    # Build the layout
    tab_layout = dbc.Container(
        [
            dbc.Row([
                dbc.Col(
                    dbc.Card(
                        dag.AgGrid(
                            id=f'{dimension_name}-table',
                            columnDefs=column_defs,
                            rowData=summary_df.to_dict('records'),
                            defaultColDef={"resizable": True},
                            dashGridOptions={
                                "rowSelection": {"mode": "multiRow"},
                                "animateRows": False,
                            },
                            style={"height": "400px"},
                        ),
                    ),
                    width={'size': 12}
                ),],
                justify='start'
            ),
            dbc.Row([
                dbc.Col(
                    dcc.Dropdown(
                        id=f'{dimension_name}-interval-dropdown',
                        options=INTERVALS,
                        value=DEFAULT_INTERVAL,
                        placeholder='Select interval',
                    ),
                    width={'offset': 1, 'size': 3}
                ),
            ],),
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        dcc.Graph(
                            id=f'{dimension_name}-history-graph',
                        ),
                    ),
                    width={'size': 12}
                ),
                justify='start'
            ),
        ],
        fluid=True
    )

    return tab_layout

from dash import callback, dcc, Input, Output, html, no_update
import dash_ag_grid as dag
import plotly.express as px
import pandas as pd
from pandas.tseries.offsets import DateOffset

from visualization.dash.portfolio_dashboard.globals import *
import dash_mantine_components as dmc


def create_dimension_tab(dimension_name, column_name, summary_df_attr, history_df_attr, tab_id):
    """Factory function to create a dimension tab (sectors, asset_types, etc.)

    Args:
        dimension_name: Tab identifier used in component IDs (e.g. "sectors")
        column_name: DataFrame column name for the dimension (e.g. "Sector")
        summary_df_attr: Attribute name on DASH_HANDLER for summary DataFrame
        history_df_attr: Attribute name on DASH_HANDLER for history DataFrame
        tab_id: The tab ID used in the main Tabs component (e.g. "sectors-dash-tab")

    Returns:
        dmc.Container layout for the tab
    """
    # Cache for lazy-loaded data (populated on first tab visit)
    _cache = {}

    def _get_data():
        """Load data on first access and cache it."""
        if 'summary_df' not in _cache:
            summary_df = getattr(DASH_HANDLER, summary_df_attr)
            _cache['summary_df'] = summary_df
            _cache['column_defs'] = [
                {"field": col, "sortable": True, "filter": True,
                 "checkboxSelection": (col == column_name),
                 "headerCheckboxSelection": (col == column_name)}
                for col in summary_df.columns
            ]
            _cache['row_data'] = summary_df.to_dict('records')
        return _cache

    # Register the combined table + graph update callback
    @callback(
        Output(f'{dimension_name}-table', 'columnDefs'),
        Output(f'{dimension_name}-table', 'rowData'),
        Output(f'{dimension_name}-history-graph', 'figure'),
        Input('tabs', 'value'),
        Input(f'{dimension_name}-table', 'selectedRows'),
        Input(f'{dimension_name}-interval-dropdown', 'value'))
    def update_tab(active_tab, selected_rows, interval):
        if active_tab != tab_id:
            return no_update, no_update, no_update

        data = _get_data()
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

        return data['column_defs'], data['row_data'], fig

    # Build the layout with empty table (populated on first tab visit)
    tab_layout = dmc.Container(
        [
            dmc.Grid([
                dmc.GridCol(
                    dmc.Paper(
                        dag.AgGrid(
                            id=f'{dimension_name}-table',
                            columnDefs=[],
                            rowData=[],
                            defaultColDef={"resizable": True},
                            dashGridOptions={
                                "rowSelection": {"mode": "multiRow"},
                                "animateRows": False,
                            },
                            style={"height": "400px"},
                        ),
                        shadow="sm", p="md",
                    ),
                    span=12,
                ),
            ]),
            dmc.Grid([
                dmc.GridCol(
                    dcc.Dropdown(
                        id=f'{dimension_name}-interval-dropdown',
                        options=INTERVALS,
                        value=DEFAULT_INTERVAL,
                        placeholder='Select interval',
                    ),
                    span=3, offset=1,
                ),
            ]),
            dmc.Grid([
                dmc.GridCol(
                    dmc.Paper(
                        dcc.Graph(
                            id=f'{dimension_name}-history-graph',
                        ),
                        shadow="sm", p="md",
                    ),
                    span=12,
                ),
            ]),
        ],
        fluid=True,
    )

    return tab_layout

from dash import callback, dcc, Input, Output, html
import dash_ag_grid as dag
import plotly.express as px
import plotly.graph_objs as go
import pandas as pd

from visualization.dash.portfolio_dashboard.globals import *
from pandas.tseries.offsets import DateOffset

import dash_bootstrap_components as dbc

# Get assets table and prepare to be displayed
assets_table_df = DASH_HANDLER.assets_summary_df
assets_table_df = assets_table_df.rename(columns={'Lifetime Return': 'Lifetime'})

# Build column definitions for ag-grid
column_defs = [{"field": col, "sortable": True, "filter": True,
                "checkboxSelection": (col == "Symbol"),
                "headerCheckboxSelection": (col == "Symbol")}
               for col in assets_table_df.columns]

# Retrieve dropdown options for filtering
sectors = sorted([{'label': x, 'value': x}
                  for x in assets_table_df['Sector'].unique()],
                 key=lambda x: x['label'])

asset_types = sorted([{'label': x, 'value': x}
                      for x in assets_table_df['AssetType'].unique()],
                     key=lambda x: x['label'])

account_types = sorted([{'label': x, 'value': x}
                        for x in assets_table_df['AccountType'].unique()],
                       key=lambda x: x['label'])

geography = sorted([{'label': x, 'value': x}
                    for x in assets_table_df['Geography'].unique()],
                   key=lambda x: x['label'])


@callback(
    Output('assets-table', 'rowData'),
    Input('sector-select-dropdown', 'value'),
    Input('asset-type-select-dropdown', 'value'),
    Input('account-type-select-dropdown', 'value'),
    Input('geography-select-dropdown', 'value'),
    Input('assets-interval-dropdown', 'value')
)
def update_assets_table(sectors_sel, asset_types_sel, account_types_sel, geography_sel, interval):
    try:
        df = assets_table_df.copy()

        # Sort by the selected interval column
        df = df.sort_values(by=interval, ascending=False)

        # Filter by dropdown selections (union of all filters)
        if sectors_sel or asset_types_sel or account_types_sel or geography_sel:
            masks = []
            if sectors_sel:
                masks.append(df['Sector'].isin(sectors_sel))
            if asset_types_sel:
                masks.append(df['AssetType'].isin(asset_types_sel))
            if account_types_sel:
                masks.append(df['AccountType'].isin(account_types_sel))
            if geography_sel:
                masks.append(df['Geography'].isin(geography_sel))

            # Union of all filter masks
            combined_mask = masks[0]
            for mask in masks[1:]:
                combined_mask = combined_mask | mask
            df = df[combined_mask]

        return df.to_dict('records')
    except Exception as e:
        print(f"Error in update_assets_table: {e}")
        return []


@callback(
    Output('assets-history-graph', 'figure'),
    Input('assets-table', 'selectedRows'),
    Input('assets-interval-dropdown', 'value'))
def update_assets_hist_graph(selected_rows, interval):
    try:
        # Use precomputed expanded data
        expanded_df = DASH_HANDLER.portfolio_assets_history_expanded_df

        # Filter by selected rows
        if selected_rows:
            selected_symbols = [row['Symbol'] for row in selected_rows]
            expanded_df = expanded_df[expanded_df['Symbol'].isin(selected_symbols)]

        # Filter by interval
        if interval != "Lifetime":
            interval_days = {k: v for (k, v) in DASH_HANDLER.performance_milestones}
            days = interval_days.get(interval, 365)
            offset = DateOffset(days=days)
            start_date = (pd.to_datetime('today') - offset).date()
            expanded_df = expanded_df[expanded_df['Date'] >= start_date]

        if expanded_df.empty:
            return go.Figure().update_layout(
                title="No data available. Select assets from the table above.")

        fig = px.line(
            expanded_df,
            x=expanded_df['Date'],
            y=expanded_df['ClosingPrice % Change'],
            hover_data={'Value': ':$,.2f', 'ClosingPrice % Change': ':.2f%'},
            color=expanded_df['Symbol'],
            line_dash=expanded_df['Sector'],
        )
        fig.update_layout(height=800)
        fig.update_yaxes(ticksuffix="%")

        return fig
    except Exception as e:
        print(f"Error in update_assets_hist_graph: {e}")
        return go.Figure().update_layout(title=f"Error loading chart: {str(e)}")

assets_tab = dbc.Container(
    [
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dag.AgGrid(
                        id='assets-table',
                        columnDefs=column_defs,
                        rowData=assets_table_df.to_dict('records'),
                        defaultColDef={"resizable": True},
                        dashGridOptions={
                            "rowSelection": {"mode": "multiRow"},
                            "animateRows": False,
                            "pagination": True,
                            "paginationPageSize": 50,
                        },
                        style={"height": "600px"},
                    ),
                ),
                width={'size': 12}
            ),],
            justify='start'
        ),
        dbc.Row([
            dbc.Col(
                dcc.Dropdown(
                    id='assets-interval-dropdown',
                    options=INTERVALS,
                    value=DEFAULT_INTERVAL,
                    placeholder='Select interval',
                ),
                width={'offset': 1, 'size': 3}
            ),
        ],),
        dbc.Row([
            dbc.Col(
                dcc.Dropdown(
                    options=sectors,
                    id='sector-select-dropdown',
                    placeholder='Select sector(s)',
                    multi=True,
                ),
                width={'offset': 1, 'size': 3}
            ),
        ],),
        dbc.Row([
            dbc.Col(
                dcc.Dropdown(
                    options=asset_types,
                    id='asset-type-select-dropdown',
                    placeholder='Select asset type(s)',
                    multi=True,
                ),
                width={'offset': 1, 'size': 3}
            ),
        ],),
        dbc.Row([
            dbc.Col(
                dcc.Dropdown(
                    options=account_types,
                    id='account-type-select-dropdown',
                    placeholder='Select account type(s)',
                    multi=True,
                ),
                width={'offset': 1, 'size': 3}
            ),
        ],),
        dbc.Row([
            dbc.Col(
                dcc.Dropdown(
                    options=geography,
                    id='geography-select-dropdown',
                    placeholder='Select geography(s)',
                    multi=True,
                ),
                width={'offset': 1, 'size': 3}
            ),
        ],),
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    dcc.Graph(
                        id='assets-history-graph',
                    ),
                ),
                width={'size': 12}
            ),
            justify='start'
        ),
    ],
    fluid=True
)

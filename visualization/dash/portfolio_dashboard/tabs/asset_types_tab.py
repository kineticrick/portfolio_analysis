from dash import callback, dcc, dash_table, Input, Output, html
import plotly.express as px
import pandas as pd

from visualization.dash.portfolio_dashboard.globals import *
from pandas.tseries.offsets import DateOffset
from libraries.pandas_helpers import print_full

import dash_bootstrap_components as dbc

# Get asset_types table and prepare to be displayed
asset_types_table_df = DASH_HANDLER.asset_types_summary_df
asset_types_table_df['id'] = asset_types_table_df['AssetType']
asset_types_table_df = asset_types_table_df.set_index('id')
columns=[{"name": i, "id": i} for i in asset_types_table_df.columns]

# Generate mapping to allow for persistent checkbox selection across 
# resorting of table 
row_asset_type_mapping = {row: asset_type
                      for row, asset_type
                      in enumerate(asset_types_table_df['AssetType'])}

@callback(
    Output('asset_types-table-container', 'children'),
    Input('asset_types-table', 'selected_rows'),
    Input('asset_types-interval-dropdown', 'value')
)
def update_asset_types_table(selected_rows, interval): 
    global asset_types_table_df, row_asset_type_mapping

    # Using current mapping, and based on incoming selected rows 
    # index numbers, get the corresponding symbols
    # NOTE: Not using selected_row_ids because it is highly 
    # unreliable and non-deterministic
    if selected_rows:
        selected_asset_types = [row_asset_type_mapping[row] for row in selected_rows]

    # Sort by interval given (ie "3m" = sort all assets 
    # by best returns over 3 months)
    # asset_types_table_df = asset_types_table_df.sort_values(by=interval, ascending=False)
    
    # Rebuild row:asset_type mapping, since the ordering of the asset_types has now changed
    row_asset_type_mapping = {row: asset_type 
                          for row, asset_type 
                          in enumerate(asset_types_table_df['AssetType'])}
    
    # Based on "selected_asset_types" above, now get the corresponding 
    # row index to indicate which rows should be selected
    if selected_rows:
        selected_rows = [row for row, asset_type in row_asset_type_mapping.items() 
                         if asset_type in selected_asset_types]
    else: 
        selected_rows = []

    data_table = dash_table.DataTable(
        id='asset_types-table',
        columns = columns,
        data=asset_types_table_df.to_dict('records'),
        style_header={
            'whiteSpace': 'normal',
            'height': 'auto',
        },
        style_cell={
            'textAlign': 'center',
            'fontSize': '13px',
        },
        fixed_rows={'headers': True},
        sort_action='native',
        sort_mode='multi',
        row_selectable='multi',
        selected_rows=selected_rows,
    )

    return data_table

@callback(
    Output('asset_types-history-graph', 'figure'),
    Input('asset_types-table', 'selected_rows'),
    Input('asset_types-interval-dropdown', 'value'))
def update_asset_types_hist_graph(selected_rows, interval):
    # Generate base dataframe containing all history for all asset_types
    asset_types_history_df = DASH_HANDLER.asset_types_history_df

    # Filter data based on the symbols selected via checkbox in the data table
    if selected_rows:
        selected_asset_types = [row_asset_type_mapping[row] for row in selected_rows]
        asset_types_history_df = asset_types_history_df[
            asset_types_history_df['AssetType'].isin(selected_asset_types)]

    # If 'Lifetime' is the interval, then we dont need to filter by date
    # Otherwise, reduce data to only include data from the start date
    if interval != "Lifetime":
        # Determine number of days to display for each asset_type
        interval_days = {k:v for (k,v) in DASH_HANDLER.performance_milestones}

        days = interval_days[interval]
        offset = DateOffset(days=days)
        start_date =  pd.to_datetime('today') - offset
        start_date = start_date.date()

        asset_types_history_df = \
            asset_types_history_df[asset_types_history_df['Date'] >= start_date]

    # asset_types_history_df = DASH_HANDLER.expand_history_df(asset_types_history_df, id_column="AssetType")
    
    # Generate Dash line graph for asset_types
    asset_types_history_fig = px.line(
        asset_types_history_df,
        x=asset_types_history_df['Date'], 
        y=asset_types_history_df['AvgPercentReturn'],
        # y=asset_types_history_df['Value % Change'],
        hover_data={'AvgPercentReturn': ':.2f%'},
        color=asset_types_history_df['AssetType'],
        # line_dash=asset_types_history_df['AssetType'],
    )
    asset_types_history_fig.update_layout(height=800)
    asset_types_history_fig.update_yaxes(ticksuffix="%")

    return asset_types_history_fig

asset_types_tab = dbc.Container(
    [        
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    html.Div(
                        id='asset_types-table-container',
                        children=[
                            dash_table.DataTable(
                                id='asset_types-table',
                                style_header={
                                    'whiteSpace': 'normal',
                                    'height': 'auto',
                                }, 
                                style_cell={
                                    'textAlign': 'center',
                                    'fontSize': '13px',
                                },
                                fixed_rows={'headers': True},
                                sort_action='native',
                                sort_mode='multi',
                                row_selectable='multi',
                            ),
                        ],
                    ),
                ),
                width={'size': 12}
            ),],
            justify='start'
        ),
        dbc.Row([
            dbc.Col(
                dcc.Dropdown(
                    # options=[{'label': i, 'value': i} for i in asset_types_intervals],
                    id='asset_types-interval-dropdown',
                    options= INTERVALS,
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
                        id='asset_types-history-graph',
                        # figure=asset_types_history_fig
                    ),
                ),
                width={'size': 12}
            ),
            justify='start'
        ),
    ],
    fluid=True
)
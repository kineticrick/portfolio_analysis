from dash import callback, dcc, dash_table, Input, Output 
import plotly.express as px
import pandas as pd

from visualization.dash.portfolio_dashboard.globals import *
from pandas.tseries.offsets import DateOffset
from libraries.pandas_helpers import print_full

import dash_bootstrap_components as dbc

@callback(
    Output('assets-table', 'columns'),
    Output('assets-table', 'data'),
    Input('assets-interval-dropdown', 'value')
)
def update_assets_table(interval): 
    # Get basis for data table/spreadsheet for assets
    assets_table_df = DASH_HANDLER.assets_summary_df
    
    # Add id column to dataframe, to be used in row selection 
    if 'id' not in assets_table_df.columns:
        assets_table_df['id'] = assets_table_df['Symbol']
        assets_table_df = assets_table_df.set_index('id')
    
    # Rename Lifetime column to just the interval name 
    assets_table_df = assets_table_df.rename(
        columns={'Lifetime Return': 'Lifetime'})  

    columns=[{"name": i, "id": i} for i in assets_table_df.columns]

    # Sort by interval given (ie "3m" = sort all assets 
    # by best returns over 3 months)
    assets_table_df = assets_table_df.sort_values(by=interval, ascending=False)
    
    return columns, assets_table_df.to_dict('records')

@callback(
    Output('assets-history-graph', 'figure'),
    Input('assets-table', 'selected_row_ids'),
    Input('assets-interval-dropdown', 'value'))
def update_assets_hist_graph(selected_row_ids, interval):
    # Generate base dataframe containing all history for all assets
    assets_history_df = DASH_HANDLER.portfolio_assets_history_df

    if selected_row_ids:
        assets_history_df = assets_history_df[
            assets_history_df['Symbol'].isin(selected_row_ids)]

    # If 'Lifetime' is the interval, then we dont need to filter by date
    # Otherwise, reduce data to only include data from the start date
    if interval != "Lifetime":
        # Determine number of days to display for each asset
        interval_days = {k:v for (k,v) in DASH_HANDLER.performance_milestones}

        days = interval_days[interval]
        offset = DateOffset(days=days)
        start_date =  pd.to_datetime('today') - offset
        start_date = start_date.date()

        assets_history_df = \
            assets_history_df[assets_history_df['Date'] >= start_date]

    assets_history_df = DASH_HANDLER.expand_history_df(assets_history_df)
    
    # Generate Dash line graph for assets
    assets_history_fig = px.line(
        assets_history_df,
        x=assets_history_df['Date'], 
        y=assets_history_df['ClosingPrice % Change'],
        color=assets_history_df['Symbol'],
        line_dash=assets_history_df['Sector'],
    )
    assets_history_fig.update_layout(height=800)

    return assets_history_fig

assets_tab = dbc.Container(
    [        
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dash_table.DataTable(
                        id='assets-table',
                        # columns=[{"name": i, "id": i}
                        #     for i in assets_table_df.columns],
                        # data=assets_table_df.to_dict('records'),
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
                ),
                width={'size': 12}
            ),],
            justify='start'
        ),
        dbc.Row([
            dbc.Col(
                dcc.Dropdown(
                    # options=[{'label': i, 'value': i} for i in INTERVALS],
                    id='assets-interval-dropdown',
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
                        id='assets-history-graph',
                        # figure=assets_history_fig
                    ),
                ),
                width={'size': 12}
            ),
            justify='start'
        ),
    ],
    fluid=True
)
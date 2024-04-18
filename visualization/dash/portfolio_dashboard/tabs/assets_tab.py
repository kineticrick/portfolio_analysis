from dash import callback, dcc, dash_table, Input, Output, html
import plotly.express as px
import pandas as pd

from visualization.dash.portfolio_dashboard.globals import *
from pandas.tseries.offsets import DateOffset
from libraries.pandas_helpers import print_full

import dash_bootstrap_components as dbc

# Get assets table and prepare to be displayed
assets_table_df = DASH_HANDLER.assets_summary_df
assets_table_df['id'] = assets_table_df['Symbol']
assets_table_df = assets_table_df.set_index('id')
assets_table_df = assets_table_df.rename(columns={'Lifetime Return': 'Lifetime'})  
columns=[{"name": i, "id": i} for i in assets_table_df.columns]

# Generate mapping to allow for persistent checkbox selection across 
# resorting of table 
row_symbol_mapping = {row: symbol 
                      for row, symbol 
                      in enumerate(assets_table_df['Symbol'])}

@callback(
    Output('assets-table-container', 'children'),
    Input('assets-table', 'selected_rows'),
    Input('assets-interval-dropdown', 'value')
)
def update_assets_table(selected_rows, interval): 
    # Using current mapping, and based on incoming selected rows 
    # index numbers, get the corresponding symbols
    # NOTE: Not using selected_row_ids because it is highly 
    # unreliable and non-deterministic
    global assets_table_df, row_symbol_mapping
    if selected_rows:
        selected_symbols = [row_symbol_mapping[row] for row in selected_rows]

    # Sort by interval given (ie "3m" = sort all assets 
    # by best returns over 3 months)
    assets_table_df = assets_table_df.sort_values(by=interval, ascending=False)
    
    # Rebuild row:symbol mapping, since the ordering of the symbols has now changed
    row_symbol_mapping = {row: symbol 
                          for row, symbol 
                          in enumerate(assets_table_df['Symbol'])}
    
    # Based on "selected_symbols" above, now get the corresponding 
    # row index to indicate which rows should be selected
    if selected_rows:
        selected_rows = [row for row, symbol in row_symbol_mapping.items() 
                         if symbol in selected_symbols]
    else: 
        selected_rows = []

    data_table = dash_table.DataTable(
        id='assets-table',
        columns = columns,
        data=assets_table_df.to_dict('records'),
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
    Output('assets-history-graph', 'figure'),
    Input('assets-table', 'selected_rows'),
    Input('assets-interval-dropdown', 'value'))
def update_assets_hist_graph(selected_rows, interval):
    # Generate base dataframe containing all history for all assets
    assets_history_df = DASH_HANDLER.portfolio_assets_history_df

    # Filter data based on the symbols selected via checkbox in the data table
    if selected_rows:
        selected_symbols = [row_symbol_mapping[row] for row in selected_rows]
        assets_history_df = assets_history_df[
            assets_history_df['Symbol'].isin(selected_symbols)]

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
                    html.Div(
                        id='assets-table-container',
                        children=[
                            dash_table.DataTable(
                                id='assets-table',
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
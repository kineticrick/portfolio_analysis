from dash import callback, dcc, dash_table, Input, Output, html
import plotly.express as px
import pandas as pd

from visualization.dash.portfolio_dashboard.globals import *
from pandas.tseries.offsets import DateOffset
from libraries.pandas_helpers import print_full

import dash_bootstrap_components as dbc

# Get geography table and prepare to be displayed
geography_table_df = DASH_HANDLER.geography_summary_df
geography_table_df['id'] = geography_table_df['Geography']
geography_table_df = geography_table_df.set_index('id')
columns=[{"name": i, "id": i} for i in geography_table_df.columns]

# Generate mapping to allow for persistent checkbox selection across 
# resorting of table 
row_account_type_mapping = {row: account_type
                      for row, account_type
                      in enumerate(geography_table_df['Geography'])}

@callback(
    Output('geography-table-container', 'children'),
    Input('geography-table', 'selected_rows'),
    Input('geography-interval-dropdown', 'value')
)
def update_geography_table(selected_rows, interval): 
    global geography_table_df, row_account_type_mapping

    # Using current mapping, and based on incoming selected rows 
    # index numbers, get the corresponding symbols
    # NOTE: Not using selected_row_ids because it is highly 
    # unreliable and non-deterministic
    if selected_rows:
        selected_geography = [row_account_type_mapping[row] for row in selected_rows]

    # Sort by interval given (ie "3m" = sort all assets 
    # by best returns over 3 months)
    # geography_table_df = geography_table_df.sort_values(by=interval, ascending=False)
    
    # Rebuild row:account_type mapping, since the ordering of the geography has now changed
    row_account_type_mapping = {row: account_type 
                          for row, account_type 
                          in enumerate(geography_table_df['Geography'])}
    
    # Based on "selected_geography" above, now get the corresponding 
    # row index to indicate which rows should be selected
    if selected_rows:
        selected_rows = [row for row, account_type in row_account_type_mapping.items() 
                         if account_type in selected_geography]
    else: 
        selected_rows = []

    data_table = dash_table.DataTable(
        id='geography-table',
        columns = columns,
        data=geography_table_df.to_dict('records'),
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
    Output('geography-history-graph', 'figure'),
    Input('geography-table', 'selected_rows'),
    Input('geography-interval-dropdown', 'value'))
def update_geography_hist_graph(selected_rows, interval):
    # Generate base dataframe containing all history for all geography
    geography_history_df = DASH_HANDLER.geography_history_df

    # Filter data based on the symbols selected via checkbox in the data table
    if selected_rows:
        selected_geography = [row_account_type_mapping[row] for row in selected_rows]
        geography_history_df = geography_history_df[
            geography_history_df['Geography'].isin(selected_geography)]

    # If 'Lifetime' is the interval, then we dont need to filter by date
    # Otherwise, reduce data to only include data from the start date
    if interval != "Lifetime":
        # Determine number of days to display for each account_type
        interval_days = {k:v for (k,v) in DASH_HANDLER.performance_milestones}

        days = interval_days[interval]
        offset = DateOffset(days=days)
        start_date =  pd.to_datetime('today') - offset
        start_date = start_date.date()

        geography_history_df = \
            geography_history_df[geography_history_df['Date'] >= start_date]

    # geography_history_df = DASH_HANDLER.expand_history_df(geography_history_df, id_column="Account Type")
    
    # Generate Dash line graph for geography
    geography_history_fig = px.line(
        geography_history_df,
        x=geography_history_df['Date'], 
        y=geography_history_df['AvgPercentReturn'],
        # y=geography_history_df['Value % Change'],
        hover_data={'AvgPercentReturn': ':.2f%'},
        color=geography_history_df['Geography'],
        # line_dash=geography_history_df['Geography'],
    )
    geography_history_fig.update_layout(height=800)
    geography_history_fig.update_yaxes(ticksuffix="%")

    return geography_history_fig

geography_tab = dbc.Container(
    [        
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    html.Div(
                        id='geography-table-container',
                        children=[
                            dash_table.DataTable(
                                id='geography-table',
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
                    # options=[{'label': i, 'value': i} for i in geography_intervals],
                    id='geography-interval-dropdown',
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
                        id='geography-history-graph',
                        # figure=geography_history_fig
                    ),
                ),
                width={'size': 12}
            ),
            justify='start'
        ),
    ],
    fluid=True
)
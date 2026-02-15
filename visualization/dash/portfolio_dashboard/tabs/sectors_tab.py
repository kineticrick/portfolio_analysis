from dash import callback, dcc, dash_table, Input, Output, html
import plotly.express as px
import pandas as pd

from visualization.dash.portfolio_dashboard.globals import *
from pandas.tseries.offsets import DateOffset
from libraries.pandas_helpers import print_full

import dash_bootstrap_components as dbc

# Get sectors table and prepare to be displayed
sectors_table_df = DASH_HANDLER.sectors_summary_df
sectors_table_df['id'] = sectors_table_df['Sector']
sectors_table_df = sectors_table_df.set_index('id')
columns=[{"name": i, "id": i} for i in sectors_table_df.columns]

# Generate mapping to allow for persistent checkbox selection across 
# resorting of table 
row_sector_mapping = {row: sector
                      for row, sector
                      in enumerate(sectors_table_df['Sector'])}

@callback(
    Output('sectors-table-container', 'children'),
    Input('sectors-table', 'selected_rows'),
    Input('sectors-interval-dropdown', 'value')
)
def update_sectors_table(selected_rows, interval): 
    global sectors_table_df, row_sector_mapping

    # Using current mapping, and based on incoming selected rows 
    # index numbers, get the corresponding symbols
    # NOTE: Not using selected_row_ids because it is highly 
    # unreliable and non-deterministic
    if selected_rows:
        selected_sectors = [row_sector_mapping[row] for row in selected_rows]

    # Sort by interval given (ie "3m" = sort all assets 
    # by best returns over 3 months)
    # sectors_table_df = sectors_table_df.sort_values(by=interval, ascending=False)
    
    # Rebuild row:sector mapping, since the ordering of the sectors has now changed
    row_sector_mapping = {row: sector 
                          for row, sector 
                          in enumerate(sectors_table_df['Sector'])}
    
    # Based on "selected_sectors" above, now get the corresponding 
    # row index to indicate which rows should be selected
    if selected_rows:
        selected_rows = [row for row, sector in row_sector_mapping.items() 
                         if sector in selected_sectors]
    else: 
        selected_rows = []

    data_table = dash_table.DataTable(
        id='sectors-table',
        columns = columns,
        data=sectors_table_df.to_dict('records'),
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
    Output('sectors-history-graph', 'figure'),
    Input('sectors-table', 'selected_rows'),
    Input('sectors-interval-dropdown', 'value'))
def update_sectors_hist_graph(selected_rows, interval):
    # Generate base dataframe containing all history for all sectors
    sectors_history_df = DASH_HANDLER.sectors_history_df

    # Filter data based on the symbols selected via checkbox in the data table
    if selected_rows:
        selected_sectors = [row_sector_mapping[row] for row in selected_rows]
        sectors_history_df = sectors_history_df[
            sectors_history_df['Sector'].isin(selected_sectors)]

    # If 'Lifetime' is the interval, then we dont need to filter by date
    # Otherwise, reduce data to only include data from the start date
    if interval != "Lifetime":
        # Determine number of days to display for each sector
        interval_days = {k:v for (k,v) in DASH_HANDLER.performance_milestones}

        days = interval_days[interval]
        offset = DateOffset(days=days)
        start_date =  pd.to_datetime('today') - offset
        start_date = start_date.date()

        sectors_history_df = \
            sectors_history_df[sectors_history_df['Date'] >= start_date]

    # sectors_history_df = DASH_HANDLER.expand_history_df(sectors_history_df, id_column="Sector")
    
    # Generate Dash line graph for sectors
    sectors_history_fig = px.line(
        sectors_history_df,
        x=sectors_history_df['Date'], 
        y=sectors_history_df['AvgPercentReturn'],
        # y=sectors_history_df['Value % Change'],
        hover_data={'AvgPercentReturn': ':.2f%'},
        color=sectors_history_df['Sector'],
        # line_dash=sectors_history_df['Sector'],
    )
    sectors_history_fig.update_layout(height=800)
    sectors_history_fig.update_yaxes(ticksuffix="%")

    return sectors_history_fig

sectors_tab = dbc.Container(
    [        
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    html.Div(
                        id='sectors-table-container',
                        children=[
                            dash_table.DataTable(
                                id='sectors-table',
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
                    # options=[{'label': i, 'value': i} for i in sectors_intervals],
                    id='sectors-interval-dropdown',
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
                        id='sectors-history-graph',
                        # figure=sectors_history_fig
                    ),
                ),
                width={'size': 12}
            ),
            justify='start'
        ),
    ],
    fluid=True
)
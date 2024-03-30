from dash import callback, dcc, dash_table, Input, Output 
import plotly.express as px
import pandas as pd

from visualization.dash.portfolio_dashboard.globals import *
from pandas.tseries.offsets import DateOffset
from libraries.pandas_helpers import print_full

import dash_bootstrap_components as dbc

@callback(
    Output('sectors-table', 'columns'),
    Output('sectors-table', 'data'),
    Input('sectors-interval-dropdown', 'value')
)
def update_sectors_table(interval): 
    # Get basis for data table/spreadsheet for sectors
    sectors_table_df = DASH_HANDLER.sectors_summary_df
    
    # Add id column to dataframe, to be used in row selection 
    if 'id' not in sectors_table_df.columns:
        sectors_table_df['id'] = sectors_table_df['Sector']
        sectors_table_df = sectors_table_df.set_index('id')
    
    # Rename Lifetime column to just the interval name 
    # sectors_table_df = sectors_table_df.rename(
    #     columns={'Lifetime Return': 'Lifetime'})  

    columns=[{"name": i, "id": i} for i in sectors_table_df.columns]

    # Sort by interval given (ie "3m" = sort all sectors 
    # by best returns over 3 months)
    # sectors_table_df = sectors_table_df.sort_values(by=interval, ascending=False)
    
    return columns, sectors_table_df.to_dict('records')

@callback(
    Output('sectors-history-graph', 'figure'),
    # Input('sectors-table', 'selected_row_ids'),
    Input('sectors-interval-dropdown', 'value'))
# def update_sectors_hist_graph(selected_row_ids, interval):
def update_sectors_hist_graph(interval):
    # Generate base dataframe containing all history for all sectors
    sectors_history_df = DASH_HANDLER.sectors_history_df

    # if selected_row_ids:
    #     sectors_history_df = sectors_history_df[
    #         sectors_history_df['Symbol'].isin(selected_row_ids)]

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
        color=sectors_history_df['Sector'],
        # line_dash=sectors_history_df['Sector'],
    )
    sectors_history_fig.update_layout(height=800)

    return sectors_history_fig

sectors_tab = dbc.Container(
    [        
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dash_table.DataTable(
                        id='sectors-table',
                        # columns=[{"name": i, "id": i}
                        #     for i in sectors_table_df.columns],
                        # data=sectors_table_df.to_dict('records'),
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
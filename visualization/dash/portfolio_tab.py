from dash import callback, dcc, html, dash_table, Input, Output
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
from visualization.dash.DashboardHandler import DashboardHandler
from pandas.tseries.offsets import DateOffset
import dash_bootstrap_components as dbc

dash_handler = DashboardHandler()

NUM_WINNERS_LOSERS = 5
PORTFOLIO_DEFAULT_INTERVAL = '1d'

# Current + Milestone Values (Scalars)
current_value = dash_handler.current_portfolio_value
portfolio_milestones = dash_handler.portfolio_milestones
yesterday_value = portfolio_milestones.loc[
    portfolio_milestones['Interval'] == '1d']['Value'].values[0]
portfolio_milestones = portfolio_milestones[['Interval', 'Value', 'Value % Return']]
intervals = portfolio_milestones['Interval'].values.tolist()

@callback(
    Output('portfolio-history-graph', 'figure'),
    Input('interval-dropdown', 'value'))
def update_port_hist_graph(interval):
    interval_days = {k:v for (k,v) in dash_handler.performance_milestones}
    
    if interval == "Lifetime":
        date = port_hist_df.index[-1]
    else: 
        days = interval_days[interval]
        offset = DateOffset(days=days)
        date =  pd.to_datetime('today') - offset
        date = date.strftime('%Y-%m-%d')
        
    port_hist_df = dash_handler.portfolio_history_df
    port_hist_df = \
        port_hist_df[port_hist_df.index >= date]
        
    port_hist_df['Value'] = port_hist_df['Value'].astype(float)

    port_hist_df['perc_change'] = \
        round((port_hist_df['Value'] - port_hist_df['Value'][0]) / 
              port_hist_df['Value'][0] * 100, 2)

    fig = px.line(
        port_hist_df,
        x=port_hist_df.index,
        y=port_hist_df['Value'],
        hover_data={'Value': ':$,.2f', 'perc_change': ':.2f%'},
        markers=True,
    )

    fig.update_layout(transition_duration=500, hovermode='y unified')
    return fig

@callback(
    Output('winners-table', 'columns'),
    Output('winners-table', 'data'),
    Output('losers-table', 'columns'),
    Output('losers-table', 'data'),
    Input('interval-dropdown', 'value'))
def update_asset_tables(interval):
    winners_df = dash_handler.get_ranked_assets(
        interval, 'price', ascending=False, count=NUM_WINNERS_LOSERS)
    winners_df = winners_df[['Symbol', 'Interval', 'Current Price', 
                             'Price', 'Price % Return']]
    winners_columns=[{"name": i, "id": i} for i in winners_df.columns]
    winners_data = winners_df.to_dict('records')

    losers_df = dash_handler.get_ranked_assets(
        interval, 'price', ascending=True, count=NUM_WINNERS_LOSERS)
    losers_df = losers_df[['Symbol', 'Interval', 'Current Price', 
                           'Price', 'Price % Return']]
    losers_columns = [{"name": i, "id": i} for i in losers_df.columns]
    losers_data = losers_df.to_dict('records')
    
    return winners_columns, winners_data, losers_columns, losers_data

@callback(
    Output('portfolio-value-scalar', 'figure'),
    Input('interval-dropdown', 'value'))
def update_portfolio_value(interval):
    milestone_value = portfolio_milestones.loc[
        portfolio_milestones['Interval'] == interval]['Value'].values[0]
    
    port_value_fig = go.Figure()

    port_value_fig.add_trace(go.Indicator(
        mode = "number+delta",
        value = current_value,
        number = {'valueformat': '$,.2f'},
        # domain = {'x': [0, 0.5], 'y': [0, 0.5]},
        delta = {'reference': milestone_value, 
                'relative': False, 
                'position' : "bottom", 
                'valueformat': '$,.2f'}
        ))

    port_value_fig.update_layout(
        paper_bgcolor = "lightblue",
        height=200,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    
    return port_value_fig

portfolio_tab = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H1("Portfolio Dashboard"),
                width={'size': 6, 'offset': 3}
            ),
            justify='center'
        ),
        html.Hr(),
        dbc.Row([
            dbc.Col(        
                html.Div([
                    "Select period:", 
                    dcc.Dropdown(
                        id='interval-dropdown',
                        options=intervals, 
                        value=PORTFOLIO_DEFAULT_INTERVAL,
                    ),
                ],),
                width={'size': 1, 'offset': 8}
            ),],
            justify='start',
        ),
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dcc.Graph(
                        id='portfolio-history-graph',
                        # figure=port_hist_fig
                    ),
                ),
                width={'size': 9}
            ),
            dbc.Col(
                dbc.Card(
                    dbc.Stack([
                        dcc.Graph(
                            id='portfolio-value-scalar',
                            # figure=port_value_fig, 
                        ),
                        dash_table.DataTable(
                            id='portfolio-milestones-table',
                            columns=[{"name": i, "id": i} 
                                for i in portfolio_milestones.columns],
                            data=portfolio_milestones.to_dict('records'),
                        )], 
                        gap=3
                    ), 
                ),
                width={'size': 3}
            )],
            justify='start'   
        ),
        dbc.Row([
            dbc.Col(
            dbc.Card(
                    dash_table.DataTable(
                        id='winners-table',
                        # columns=[{"name": i, "id": i}
                        #     for i in winners_df.columns],
                        # data=winners_df.to_dict('records'),
                    ),
                ),
                width={'size': 3, 'offset': 1},  
            ), 
            dbc.Col(
            dbc.Card(
                    dash_table.DataTable(
                        id='losers-table',
                        # columns=[{"name": i, "id": i}
                        #     for i in losers_df.columns],
                        # data=losers_df.to_dict('records'),
                    ),
                ),
                width={'size': 3, 'offset': 1},  
            ),],
            justify='start'
        ),
    ], 
    fluid=True
)
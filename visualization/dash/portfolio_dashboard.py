from dash import (Dash, dcc, html, 
                  Input, Output, callback, dash_table)
import plotly.express as px
import plotly.graph_objects as go

import pandas as pd
import numpy as np

import os 
import sys 

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from libraries.pandas_helpers import print_full
from pandas.tseries.offsets import DateOffset
from libraries.vars import BUSINESS_CADENCE_MAP
from visualization.dash.DashboardHandler import DashboardHandler

import dash_bootstrap_components as dbc

dash_handler = DashboardHandler()

# Current + Milestone Values (Scalars)
current_value = dash_handler.current_portfolio_value
portfolio_milestones = dash_handler.portfolio_milestones
yesterday_value = portfolio_milestones.loc[
    portfolio_milestones['Interval'] == '1d']['Value'].values[0]
portfolio_milestones = portfolio_milestones[['Interval', 'Value', 'Value % Return']]
intervals = portfolio_milestones['Interval'].values.tolist()

# Historical graph data
port_hist_df = dash_handler.portfolio_history_df


# Winners
num_winners_losers = 5
default_interval = '1d'
winners_df = dash_handler.get_ranked_assets(
    default_interval, 'price', ascending=False, count=num_winners_losers)
winners_df = winners_df[['Symbol', 'Interval', 'Current Price', 'Price', 'Price % Return']]

# Losers
losers_df = dash_handler.get_ranked_assets(
    default_interval, 'price', ascending=True, count=num_winners_losers)
losers_df = losers_df[['Symbol', 'Interval', 'Current Price', 'Price', 'Price % Return']]

port_value_fig = go.Figure()

port_value_fig.add_trace(go.Indicator(
    mode = "number+delta",
    value = current_value,
    number = {'valueformat': '$,.2f'},
    # domain = {'x': [0, 0.5], 'y': [0, 0.5]},
    delta = {'reference': yesterday_value, 
             'relative': False, 
             'position' : "bottom", 
             'valueformat': '$,.2f'}
    ))

port_value_fig.update_layout(
    paper_bgcolor = "lightblue",
    height=200,
    margin=dict(l=10, r=10, t=10, b=10),
)


app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

portfolio_dash_tab = dbc.Container(
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
                        value=default_interval,
                        clearable=False,
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
                        columns=[{"name": i, "id": i}
                            for i in winners_df.columns],
                        data=winners_df.to_dict('records'),
                    ),
                ),
                width={'size': 3, 'offset': 1},  
            ), 
            dbc.Col(
            dbc.Card(
                    dash_table.DataTable(
                        id='losers-table',
                        columns=[{"name": i, "id": i}
                            for i in losers_df.columns],
                        data=losers_df.to_dict('records'),
                    ),
                ),
                width={'size': 3, 'offset': 1},  
            ),],
            justify='start'
        ),
    ], 
    fluid=True
)


asset_hypo_df = dash_handler.assets_hypothetical_history_df

asset_hypo_fig = px.line(
    asset_hypo_df,
    x=asset_hypo_df['Date'], 
    y=asset_hypo_df['ClosingPrice'],
    color=asset_hypo_df['Symbol'],
    line_dash=asset_hypo_df['Owned'],
)
asset_hypo_fig.update_layout(height=800)

normalized_hypo_df = dash_handler.exits_hypotheticals_history_df
normalized_hypo_df = dash_handler.expand_history_df(normalized_hypo_df)

normalized_hypo_fig = px.line(
    normalized_hypo_df,
    x=normalized_hypo_df['Date'], 
    y=normalized_hypo_df['ClosingPrice % Change'],
    color=normalized_hypo_df['Symbol'],
    line_dash=normalized_hypo_df['Sector'],
)
normalized_hypo_fig.update_layout(height=800)

sectors = normalized_hypo_df['Sector'].unique().tolist()
sectors = [{'label': x, 'value': x} for x in sectors]
sectors = sorted(sectors, key=lambda x: x['label'])


asset_hypo_stats_df = dash_handler.gen_historical_stats(asset_hypo_df, hypotheticals=True)
asset_hypo_stats_df = asset_hypo_stats_df[['Name', 'Symbol', 'Sector', 'Hypo Ret.(Exit/Current)%']]


hypotheticals_dash_tab = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    dcc.Graph(
                        id='hypothetical-history-graph',
                        figure=asset_hypo_fig
                    ),
                ),
                width={'size': 12}
            ),
            justify='start'
        ),
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
            dbc.Col(
                dcc.Dropdown(
                    id='asset-select-dropdown',
                    placeholder='Select asset(s)',
                    multi=True,
                ),
                width={'offset': 1, 'size': 3}
            ),],
            justify='start' 
        ),
        
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dcc.Graph(
                        id='hypothetical-normalized-history-graph',
                        figure=normalized_hypo_fig
                    ),
                ),
                width={'size': 9}
            ),
            dbc.Col(
                dbc.Card(
                    dash_table.DataTable(
                        id='hypos-global-table',
                        columns=[{"name": i, "id": i}
                            for i in asset_hypo_stats_df.columns],
                        data=asset_hypo_stats_df.to_dict('records'),
                        style_header={
                            'whiteSpace': 'normal',
                            'height': 'auto',
                        }, 
                        style_cell={
                            'textAlign': 'center',
                            'fontSize': '13px',
                        }
                    ),
                ),
                width={'size': 3}
            ),],
            justify='start'
        ),
    ],
    fluid=True
)
    
assets_global_table_df = dash_handler.assets_summary_df

assets_history_df = dash_handler.expand_history_df(
    dash_handler.portfolio_assets_history_df)

assets_history_fig = px.line(
    assets_history_df,
    x=assets_history_df['Date'], 
    y=assets_history_df['ClosingPrice % Change'],
    color=assets_history_df['Symbol'],
    line_dash=assets_history_df['Sector'],
)
assets_history_fig.update_layout(height=800)


assets_dash_tab = dbc.Container(
    [        
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    dash_table.DataTable(
                        id='assets-global-table',
                        columns=[{"name": i, "id": i}
                            for i in assets_global_table_df.columns],
                        data=assets_global_table_df.to_dict('records'),
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
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    dcc.Graph(
                        id='assets-history-graph',
                        figure=assets_history_fig
                    ),
                ),
                width={'size': 12}
            ),
            justify='start'
        ),
    ],
    fluid=True
)

app.layout = \
    dbc.Tabs(
        [
            dbc.Tab(label='Portfolio Dashboard', tab_id='portfolio-dash-tab', children=portfolio_dash_tab),
            dbc.Tab(label='Assets Dashboard', tab_id='assets-dash-tab', children=assets_dash_tab),
            dbc.Tab(label='Hypotheticals Dashboard', tab_id='hypotheticals-dash-tab', children=hypotheticals_dash_tab),
        ], 
        id='tabs', active_tab='assets-dash-tab'
    )

@callback(
    Output('asset-select-dropdown', 'options'),
    Input('sector-select-dropdown', 'value'))
def update_asset_dropdown_options(sectors):    
    if not sectors:
        df = normalized_hypo_df  
    else:
        df = normalized_hypo_df[normalized_hypo_df['Sector'].isin(sectors)]

    df = df[['Symbol', 'Name', ]].drop_duplicates()
    
    assets = []
    for _, row in df.iterrows():
        asset_dict = {
            'value': row['Symbol'],
            'label': f"{row['Symbol']} | {row['Name']}",
        }
        assets.append(asset_dict)
        
    assets = sorted(assets, key=lambda x: x['label'])
    
    return assets
    
@callback(
    Output('asset-select-dropdown', 'value'),
    Input('sector-select-dropdown', 'value'),
    Input('asset-select-dropdown', 'options'))
def set_asset_dropdown_values(sectors, available_options):
    if not sectors: 
        return None
    else: 
        return [x['value'] for x in available_options]

@callback(
    Output('hypothetical-normalized-history-graph', 'figure'),
    Input('sector-select-dropdown', 'value'),
    Input('asset-select-dropdown', 'value'))
def update_normalized_hypo_graph(sectors, assets):
    if not sectors and not assets:
        df = normalized_hypo_df
    else:
        df = normalized_hypo_df[normalized_hypo_df['Symbol'].isin(assets)]

    normalized_hypo_fig = px.line(
        df,
        x=df['Date'], 
        y=df['ClosingPrice % Change'],
        color=df['Symbol'],
        line_dash=df['Sector'],
    )
        
    normalized_hypo_fig.update_layout(transition_duration=500, height=800)
    return normalized_hypo_fig
        
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
    
    # raw_pct_change = port_hist_df['Value'].pct_change() * 100
    # port_hist_df['% Change'] = round(raw_pct_change, 2)

    port_hist_df['perc_change'] = \
        round((port_hist_df['Value'] - port_hist_df['Value'][0]) / 
              port_hist_df['Value'][0] * 100, 2)

    # print_full(port_hist_df)
    fig = px.line(
        port_hist_df,
        x=port_hist_df.index,
        y=port_hist_df['Value'],
        hover_data={'Value': ':$,.2f', 'perc_change': ':.2f%'},
        markers=True,
    )
    
    # fig.update_traces(
    #     hovertemplate='%{y:$,.2f}<br>%{perc.change}<extra></extra>')
    
    # y:$,.2f}<br>Change: %{perc_change:.2f%}<extra></extra>')
    
    
    fig.update_layout(transition_duration=500, hovermode='y unified')
    return fig

@callback(
    Output('winners-table', 'data'),
    Output('losers-table', 'data'),
    Input('interval-dropdown', 'value'))
def update_asset_tables(interval):
    winners_df = dash_handler.get_ranked_assets(
        interval, 'price', ascending=False, count=num_winners_losers)
    winners_df = winners_df[['Symbol', 'Interval', 'Current Price', 'Price', 'Price % Return']]

    losers_df = dash_handler.get_ranked_assets(
        interval, 'price', ascending=True, count=num_winners_losers)
    losers_df = losers_df[['Symbol', 'Interval', 'Current Price', 'Price', 'Price % Return']]
    
    return winners_df.to_dict('records'), losers_df.to_dict('records')

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

if __name__ == '__main__':
    app.run_server(debug=True)

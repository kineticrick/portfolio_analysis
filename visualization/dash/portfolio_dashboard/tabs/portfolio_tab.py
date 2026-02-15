from dash import callback, dcc, html, Input, Output
import dash_ag_grid as dag
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
from visualization.dash.portfolio_dashboard.globals import *
from pandas.tseries.offsets import DateOffset
import dash_mantine_components as dmc

# Build column defs for the static milestones table
milestones_column_defs = [{"field": col, "sortable": True, "filter": True}
                          for col in PORTFOLIO_MILESTONES.columns]

@callback(
    Output('portfolio-history-graph', 'figure'),
    Input('interval-dropdown', 'value'))
def update_port_hist_graph(interval):
    try:
        interval_days = {k:v for (k,v) in DASH_HANDLER.performance_milestones}

        port_hist_df = DASH_HANDLER.portfolio_history_df

        if interval == "Lifetime":
            date = port_hist_df.index[0]
        else:
            days = interval_days.get(interval, 365)
            offset = DateOffset(days=days)
            date = pd.to_datetime('today') - offset
            date = date.strftime('%Y-%m-%d')

        port_hist_df = port_hist_df[port_hist_df.index >= date]

        if port_hist_df.empty:
            return go.Figure().update_layout(title="No data available for selected interval")

        port_hist_df['Value'] = port_hist_df['Value'].astype(float)

        port_hist_df['perc_change'] = \
            round((port_hist_df['Value'] - port_hist_df['Value'].iloc[0]) /
                  port_hist_df['Value'].iloc[0] * 100, 2)

        fig = px.line(
            port_hist_df,
            x=port_hist_df.index,
            y=port_hist_df['Value'],
            hover_data={'Value': ':$,.2f', 'perc_change': ':.2f%'},
            markers=True,
        )

        fig.update_layout(transition_duration=500, hovermode='y unified',
                          xaxis=dict(rangeslider=dict(visible=True)))
        return fig
    except Exception as e:
        print(f"Error in update_port_hist_graph: {e}")
        return go.Figure().update_layout(title=f"Error loading portfolio history: {str(e)}")

@callback(
    Output('winners-table', 'rowData'),
    Output('winners-table', 'columnDefs'),
    Output('losers-table', 'rowData'),
    Output('losers-table', 'columnDefs'),
    Input('interval-dropdown', 'value'))
def update_asset_tables(interval):
    try:
        winners_df = DASH_HANDLER.get_ranked_assets(
            interval, 'price', ascending=False, count=NUM_WINNERS_LOSERS)
        winners_df = winners_df[['Symbol', 'Interval', 'Current Price',
                                 'Price', 'Price % Return']]
        winners_col_defs = [{"field": col, "sortable": True, "filter": True}
                            for col in winners_df.columns]

        losers_df = DASH_HANDLER.get_ranked_assets(
            interval, 'price', ascending=True, count=NUM_WINNERS_LOSERS)
        losers_df = losers_df[['Symbol', 'Interval', 'Current Price',
                               'Price', 'Price % Return']]
        losers_col_defs = [{"field": col, "sortable": True, "filter": True}
                           for col in losers_df.columns]

        return (winners_df.to_dict('records'), winners_col_defs,
                losers_df.to_dict('records'), losers_col_defs)
    except Exception as e:
        print(f"Error in update_asset_tables: {e}")
        err_col = [{"field": "Error"}]
        err_data = [{"Error": f"Error loading data: {str(e)}"}]
        return err_data, err_col, err_data, err_col

@callback(
    Output('portfolio-value-scalar', 'figure'),
    Input('interval-dropdown', 'value'))
def update_portfolio_value(interval):
    try:
        milestone_data = PORTFOLIO_MILESTONES.loc[
            PORTFOLIO_MILESTONES['Interval'] == interval]

        if milestone_data.empty:
            milestone_value = CURRENT_PORTFOLIO_VALUE
        else:
            milestone_value = milestone_data['Value'].values[0]

        port_value_fig = go.Figure()

        port_value_fig.add_trace(go.Indicator(
            mode = "number+delta",
            value = CURRENT_PORTFOLIO_VALUE,
            number = {'valueformat': '$,.2f'},
            delta = {'reference': milestone_value,
                    'relative': False,
                    'position' : "bottom",
                    'valueformat': '$,.2f'}
            ))

        port_value_fig.update_layout(
            height=200,
            margin=dict(l=10, r=10, t=10, b=10),
        )

        return port_value_fig
    except Exception as e:
        print(f"Error in update_portfolio_value: {e}")
        return go.Figure().update_layout(title=f"Error: {str(e)}")

portfolio_tab = dmc.Container(
    [
        dmc.Grid(
            dmc.GridCol(
                html.H1("Portfolio Dashboard"),
                span=6, offset=3,
            ),
            justify='center',
        ),
        html.Hr(),
        dmc.Grid([
            dmc.GridCol(
                html.Div([
                    "Select period:",
                    dcc.Dropdown(
                        id='interval-dropdown',
                        options=INTERVALS,
                        value=PORTFOLIO_DEFAULT_INTERVAL,
                    ),
                ]),
                span=1, offset=8,
            ),
        ]),
        dmc.Grid([
            dmc.GridCol(
                dmc.Paper(
                    dcc.Graph(
                        id='portfolio-history-graph',
                    ),
                    shadow="sm", p="md",
                ),
                span=9,
            ),
            dmc.GridCol(
                dmc.Paper(
                    dmc.Stack([
                        dcc.Graph(
                            id='portfolio-value-scalar',
                        ),
                        dag.AgGrid(
                            id='portfolio-milestones-table',
                            columnDefs=milestones_column_defs,
                            rowData=PORTFOLIO_MILESTONES.to_dict('records'),
                            defaultColDef={"resizable": True},
                            dashGridOptions={"domLayout": "autoHeight"},
                        )],
                        gap="md",
                    ),
                    shadow="sm", p="md",
                ),
                span=3,
            ),
        ]),
        dmc.Grid([
            dmc.GridCol(
                dmc.Paper(
                    dag.AgGrid(
                        id='winners-table',
                        columnDefs=[],
                        rowData=[],
                        defaultColDef={"resizable": True},
                        dashGridOptions={"domLayout": "autoHeight"},
                    ),
                    shadow="sm", p="md",
                ),
                span=3, offset=1,
            ),
            dmc.GridCol(
                dmc.Paper(
                    dag.AgGrid(
                        id='losers-table',
                        columnDefs=[],
                        rowData=[],
                        defaultColDef={"resizable": True},
                        dashGridOptions={"domLayout": "autoHeight"},
                    ),
                    shadow="sm", p="md",
                ),
                span=3, offset=1,
            ),
        ]),
    ],
    fluid=True,
)

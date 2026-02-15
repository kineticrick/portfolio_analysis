from dash import (callback, dcc, Input, Output)
import dash_ag_grid as dag
import plotly.express as px

from visualization.dash.portfolio_dashboard.globals import *

import dash_bootstrap_components as dbc

normalized_hypo_df = DASH_HANDLER.exits_hypotheticals_history_df
normalized_hypo_df = DASH_HANDLER.expand_history_df(normalized_hypo_df)

normalized_hypo_fig = px.line(
    normalized_hypo_df,
    x=normalized_hypo_df['Date'],
    y=normalized_hypo_df['ClosingPrice % Change'],
    color=normalized_hypo_df['Symbol'],
    line_dash=normalized_hypo_df['Sector'],
)
normalized_hypo_fig.update_layout(height=800)
normalized_hypo_fig.update_yaxes(ticksuffix="%")

sectors = normalized_hypo_df['Sector'].unique().tolist()
sectors = [{'label': x, 'value': x} for x in sectors]
sectors = sorted(sectors, key=lambda x: x['label'])

asset_hypo_df = DASH_HANDLER.assets_hypothetical_history_df
asset_hypo_stats_df = DASH_HANDLER.gen_historical_stats(asset_hypo_df, hypotheticals=True)
asset_hypo_stats_df = asset_hypo_stats_df[['Name', 'Symbol', 'Sector', 'Hypo Ret.(Exit/Current)%']]

# Build ag-grid column defs for the hypotheticals stats table
hypo_column_defs = [{"field": col, "sortable": True, "filter": True}
                    for col in asset_hypo_stats_df.columns]

@callback(
    Output('asset-select-dropdown', 'options'),
    Input('hypo-sector-select-dropdown', 'value'))
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
    Input('hypo-sector-select-dropdown', 'value'),
    Input('asset-select-dropdown', 'options'))
def set_asset_dropdown_values(sectors, available_options):
    if not sectors:
        return None
    else:
        return [x['value'] for x in available_options]

@callback(
    Output('hypothetical-normalized-history-graph', 'figure'),
    Input('hypo-sector-select-dropdown', 'value'),
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
    normalized_hypo_fig.update_yaxes(ticksuffix="%")
    return normalized_hypo_fig

hypotheticals_tab = dbc.Container(
    [
        dbc.Row([
            dbc.Col(
                dcc.Dropdown(
                    options=sectors,
                    id='hypo-sector-select-dropdown',
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
            ),
            ],
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
                    dag.AgGrid(
                        id='hypos-global-table',
                        columnDefs=hypo_column_defs,
                        rowData=asset_hypo_stats_df.to_dict('records'),
                        defaultColDef={"resizable": True},
                        dashGridOptions={"domLayout": "autoHeight"},
                    ),
                ),
                width={'size': 3}
            ),],
            justify='start'
        ),
    ],
    fluid=True
)

import os 
import sys 
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

import time
enter = time.perf_counter()

import dash_bootstrap_components as dbc
from dash import Dash

from libraries.globals import MYSQL_CACHE_ENABLED, MYSQL_CACHE_TTL

if MYSQL_CACHE_ENABLED:
    print(f"Cache enabled with TTL of {MYSQL_CACHE_TTL} seconds")
else:
    print("Cache disabled") 

print("Loading Portfolio Dashboard...")
app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

from visualization.dash.portfolio_dashboard.tabs import (
                                                         portfolio_tab, 
                                                         assets_tab,
                                                         hypotheticals_tab,
                                                         sectors_tab,
                                                         asset_types_tab, 
                                                         account_types_tab,
                                                         geography_tab)


print("Loading Portfolio Tabs...")
app.layout = \
    dbc.Tabs(
        [
            dbc.Tab(label='Portfolio', tab_id='portfolio-dash-tab', 
                    children=portfolio_tab),
            dbc.Tab(label='Sectors', tab_id='sectors-dash-tab', 
                    children=sectors_tab),
            dbc.Tab(label='Asset Types', tab_id='asset-types-dash-tab', 
                    children=asset_types_tab),
            dbc.Tab(label='Account Types', tab_id='account-types-dash-tab', 
                    children=account_types_tab),
            dbc.Tab(label='Geography', tab_id='geography-dash-tab', 
                    children=geography_tab),
            dbc.Tab(label='Assets', tab_id='assets-dash-tab', 
                    children=assets_tab),
        #     Removed hypotheticals_tab from tabs
            dbc.Tab(label='Hypotheticals', tab_id='hypotheticals-dash-tab', 
                    children=hypotheticals_tab),
        ], 
        id='tabs', 
        active_tab='assets-dash-tab'
    )

print(f'Portfolio Dashboard loaded in {time.perf_counter() - enter} seconds')

if __name__ == '__main__':
    app.run(debug=True)

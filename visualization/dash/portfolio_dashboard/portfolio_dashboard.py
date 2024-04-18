import os 
import sys 
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

import time
enter = time.perf_counter()

import dash_bootstrap_components as dbc
from dash import Dash

from visualization.dash.portfolio_dashboard.tabs import (
                                                         portfolio_tab, 
                                                         assets_tab,
                                                         hypotheticals_tab,
                                                         sectors_tab
                                                         )

from libraries.globals import MYSQL_CACHE_ENABLED, MYSQL_CACHE_TTL

if MYSQL_CACHE_ENABLED:
    print(f"Cache enabled with TTL of {MYSQL_CACHE_TTL} seconds")
else:
    print("Cache disabled") 

print("Loading Portfolio Dashboard...")
app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

print("Loading Portfolio Tabs...")
app.layout = \
    dbc.Tabs(
        [
            dbc.Tab(label='Portfolio Dashboard', tab_id='portfolio-dash-tab', 
                    children=portfolio_tab),
            dbc.Tab(label='Assets Dashboard', tab_id='assets-dash-tab', 
                    children=assets_tab),
            dbc.Tab(label='Sectors Dashboard', tab_id='sectors-dash-tab', 
                    children=sectors_tab),
        #     Removed hypotheticals_tab from tabs
            dbc.Tab(label='Hypotheticals Dashboard', tab_id='hypotheticals-dash-tab', 
                    children=hypotheticals_tab),
        ], 
        id='tabs', 
        active_tab='assets-dash-tab'
    )

print(f'Portfolio Dashboard loaded in {time.perf_counter() - enter} seconds')

if __name__ == '__main__':
    app.run_server(debug=True)
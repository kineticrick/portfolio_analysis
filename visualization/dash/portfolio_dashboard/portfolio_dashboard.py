import os 
import sys 
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

import dash_bootstrap_components as dbc
from dash import Dash

from visualization.dash.portfolio_dashboard.tabs import (portfolio_tab, 
                                                         assets_tab,
                                                         hypotheticals_tab)

app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

app.layout = \
    dbc.Tabs(
        [
            dbc.Tab(label='Portfolio Dashboard', tab_id='portfolio-dash-tab', 
                    children=portfolio_tab),
            dbc.Tab(label='Assets Dashboard', tab_id='assets-dash-tab', 
                    children=assets_tab),
            dbc.Tab(label='Hypotheticals Dashboard', tab_id='hypotheticals-dash-tab', 
                    children=hypotheticals_tab),
        ], 
        id='tabs', 
        active_tab='assets-dash-tab'
    )

if __name__ == '__main__':
    app.run_server(debug=True)

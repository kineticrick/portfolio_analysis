import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

import time
enter = time.perf_counter()

import dash_mantine_components as dmc
from dash import Dash, dcc

from libraries.globals import MYSQL_CACHE_ENABLED, MYSQL_CACHE_TTL

if MYSQL_CACHE_ENABLED:
    print(f"Cache enabled with TTL of {MYSQL_CACHE_TTL} seconds")
else:
    print("Cache disabled")

print("Loading Portfolio Dashboard...")
app = Dash(external_stylesheets=dmc.styles.ALL)

from visualization.dash.portfolio_dashboard.tabs import (
                                                         portfolio_tab,
                                                         assets_tab,
                                                         hypotheticals_tab,
                                                         sectors_tab,
                                                         asset_types_tab,
                                                         account_types_tab,
                                                         geography_tab)


print("Loading Portfolio Tabs...")
app.layout = dmc.MantineProvider(
    dcc.Loading(
        dmc.Tabs(
            value='portfolio-dash-tab',
            id='tabs',
            children=[
                dmc.TabsList([
                    dmc.TabsTab('Portfolio', value='portfolio-dash-tab'),
                    dmc.TabsTab('Sectors', value='sectors-dash-tab'),
                    dmc.TabsTab('Asset Types', value='asset-types-dash-tab'),
                    dmc.TabsTab('Account Types', value='account-types-dash-tab'),
                    dmc.TabsTab('Geography', value='geography-dash-tab'),
                    dmc.TabsTab('Assets', value='assets-dash-tab'),
                    dmc.TabsTab('Hypotheticals', value='hypotheticals-dash-tab'),
                ]),
                dmc.TabsPanel(portfolio_tab, value='portfolio-dash-tab'),
                dmc.TabsPanel(sectors_tab, value='sectors-dash-tab'),
                dmc.TabsPanel(asset_types_tab, value='asset-types-dash-tab'),
                dmc.TabsPanel(account_types_tab, value='account-types-dash-tab'),
                dmc.TabsPanel(geography_tab, value='geography-dash-tab'),
                dmc.TabsPanel(assets_tab, value='assets-dash-tab'),
                dmc.TabsPanel(hypotheticals_tab, value='hypotheticals-dash-tab'),
            ],
        )
    )
)

print(f'Portfolio Dashboard loaded in {time.perf_counter() - enter} seconds')

if __name__ == '__main__':
    app.run(debug=True)

#!/usr/bin/env python

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import plotly.express as px

from libraries.pandas_helpers import *
from libraries.helpers import gen_asset_historical_value 
from libraries.yfinancelib import get_price_data, get_summary_returns

symbols = ['MSFT','DIS']
# symbols = ['MSFT', 'KO', 'DIS', 'REGN', 'SMH', 'AAPL', 'AMZN', 'GOOG', 'META','NVDA']

out = get_summary_returns(symbols, 
                          unit="years", length=2, 
                          interval="monthly", close=True, 
                          pct_change=False)

all_assets_df = pd.DataFrame()

print(out)

for k, v in out.items():
    seed_amt = 10000
    v['pct_diff_from_start'] = round((v['Close'] - v['Close'][0]) / v['Close'][0] * 100, 2)
    v['return_from_start'] = seed_amt + (seed_amt * (v['pct_diff_from_start'] / 100))
    v['rolling_avg'] = v['Close'].rolling(window=12).mean()
    v['exponential_avg'] = v['Close'].ewm(span=12, adjust=False).mean()
    v["Symbol"] = k
    all_assets_df = pd.concat([all_assets_df, v], axis=0)
    # print(k)
    # print(type(v))
    # print_full(v)

print_full(all_assets_df)

metrics = [
    # 'pct_diff_from_start', 
    'return_from_start', 
    # 'exponential_avg',
    # 'rolling_avg',
    #  'Close',
     ]

fig = px.line(all_assets_df, x=all_assets_df.index, y=metrics, color="Symbol")
fig.show()



# ############
# hist_value_df = gen_asset_historical_value('MSFT', 'monthly')

# fig = px.line(hist_value_df, x=hist_value_df.index, 
#               y='Value', title='MSFT Value')
# fig.show()
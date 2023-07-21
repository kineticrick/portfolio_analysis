#!/usr/bin/env python

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import datetime
import pandas as pd
from pandas.tseries.offsets import BDay
from pandas.tseries.offsets import DateOffset
# from pandas.Timestamp import today
from libraries.pandas_helpers import print_full
from libraries.helpers import get_portfolio_current_value

from libraries.HistoryHandler import PortfolioHistoryHandler, AssetHistoryHandler

ph = PortfolioHistoryHandler()
history_df = ph.get_history()

history_df['Date'] = pd.to_datetime(history_df['Date'])
history_df = history_df.set_index('Date')

milestones = [
    ('1d', 1), 
    ('1w', 7),
    ('1m', 30),
    ('3m', 90),
    ('6m', 180),
    ('1y', 365),
    ('2y', 730),
    ('3y', 1095),
    ('5y', 1825),
]

portfolio_milestones = []
# portfolio_summary_df, portfolio_value = get_portfolio_current_value()
# portfolio_milestones.append({
#     'Date': pd.to_datetime('today').strftime('%Y-%m-%d'),
#     'Interval': 'Now',
#     'Value': portfolio_value,
# })
for (interval, days) in milestones:
    offset = DateOffset(days=days)
    milestone_date = pd.to_datetime('today') - offset
    milestone_date = milestone_date.strftime('%Y-%m-%d')
    # print(milestone_date)
    
    milestone_value = history_df.loc[milestone_date]['Value']
    # print(milestone_value)
    
    portfolio_milestones.append({
        'Date': milestone_date,
        'Interval': interval,
        'Value': milestone_value,
    })

milestones_df = pd.DataFrame(portfolio_milestones)
milestones_df['Value'] = milestones_df['Value'].astype(float)

# print(milestones_df.dtypes)

# pct_change = milestones_df['Value'].pct_change() * 100
# milestones_df['Percent Change'] = round(pct_change, 2)

# current_value = 545969.49

milestones_df['Percent Change'] = \
    round((current_value - milestones_df['Value']) / milestones_df['Value'] * 100, 2)
    
print_full(milestones_df)

portfolio_summary_df, portfolio_value = get_portfolio_current_value()
print_full(portfolio_summary_df)
print(portfolio_value)
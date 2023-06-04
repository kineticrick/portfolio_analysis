#!/usr/bin/env python3

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import yfinance as yf
from datetime import date
from dateutil.relativedelta import relativedelta
from libraries.pandas_helpers import * 
from libraries.vars import BUSINESS_CADENCE_MAP

# Given a type of unit and count, return the start date in the past
# For instance, "week, 2" would give the date 2 weeks ago
def get_dates_from_desc(unit, count):
    # Make sure unit is plural, to fulfill relativedelta arg requirements
    unit = unit + "s" if unit[-1] != "s" else unit
    
    assert(unit in ["days", "weeks", "months", "quarters", "years"])
    assert(isinstance(count, int) and count > 0)
    
    if unit == "quarters":
        unit = "months"
        count = count * 3
    
    today = date.today()
    date_shift_args = {unit: count * -1}
    shift = relativedelta(**date_shift_args)
    
    return today + shift

# For any given ticker, retrieve market data for the given time period
# Returns close data (as opposed to open, high, low) by default
def get_price_data(tickers, start=None, end=None, interval=None): 
    assert(isinstance(tickers, list))
    
    ticker_str = " ".join(tickers)
    
    ticker_info = {} 
    if len(tickers) == 1: 
        ticker = yf.Ticker(ticker_str)
        symbol = ticker.info['symbol']
        ticker_info[symbol] = ticker.history(start=start, end=end)
    elif len(tickers) > 1:
        ticker_objs = yf.Tickers(ticker_str)
        for sym,obj in ticker_objs.tickers.items():
            symbol = obj.info['symbol']
            ticker_info[symbol] = \
                ticker_objs.tickers[symbol].history(start=start, end=end)
    
    cadence = BUSINESS_CADENCE_MAP[interval]
    
    for symbol, data in ticker_info.items(): 
        data.index = pd.to_datetime(data.index).date
        data.index.name = 'Date'
        data.index = pd.to_datetime(data.index)
        data = data.set_index(data.index)
        
        data = data.asfreq(cadence)
        data['Symbol'] = symbol
        ticker_info[symbol] = data
    
    return ticker_info

# For the ticker, unit and length specified, retrieve summary returns 
# For instance, if unit is "months" and length is 3, returns the closing price
# for each of the last 3 months
# Currently defaults to daily data
def get_summary_returns(tickers, unit="months", length=3, 
                        interval="daily", close=True, pct_change=True
                        ):
    # interval_map = {'daily': '1d', 'weekly': '1wk', 'monthly': '1mo',
    #                 'quarterly': '3mo', 'yearly': '1y'}
    start_date = get_dates_from_desc(unit, length)
    raw_price_data = \
        get_price_data(tickers, start=start_date, interval=interval)
                
    # TODO: Pull out pct_ change to external function                
    # Add percent change column to each dataframe
    if pct_change:
        data_type = "Close" if close else "Open"
        for symbol, data in raw_price_data.items():
            raw_pct_change = data[data_type].pct_change() * 100
            raw_price_data[symbol]['Percent Change'] = \
                round(raw_pct_change, 2)
        
    return raw_price_data

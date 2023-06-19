#!/usr/bin/env python3

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import yfinance as yf

from collections import defaultdict
from datetime import date
from dateutil.relativedelta import relativedelta
from libraries.pandas_helpers import * 
from libraries.vars import BUSINESS_CADENCE_MAP, SYMBOL_BLACKLIST

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

def get_tickers_from_yfinance(tickers: list) -> dict:
    """ 
    Base retrieval function to get ticker data from yfinance
    Ensures blacklist is used, and generally standardizes all ticker calls to yfinance
    
    Returns: 
        prices(dict): {symbol: yfinance Ticker Object}

    """
    assert(isinstance(tickers, list))
    
    # Remove any symbols which no longer exist 
    # Passing a nonexistent symbol to yfinance will cause 
    # an exception which cannot be handled gracefully
    tickers = list(set(tickers) - set(SYMBOL_BLACKLIST))
    ticker_str = " ".join(tickers)
    
    ticker_info = {} 
    if len(tickers) == 1: 
        ticker = yf.Ticker(ticker_str)
        symbol = ticker.info['symbol']
        ticker_info[symbol] = ticker
    elif len(tickers) > 1:
        ticker_objs = yf.Tickers(ticker_str)
        for sym,obj in ticker_objs.tickers.items():
            symbol = obj.info['symbol']
            ticker_info[symbol] = obj
    
    return ticker_info

def get_historical_prices(tickers: list, start: str=None, 
                   end: str=None, interval: str=None) -> pd.DataFrame:
    """ 
    # For any given ticker, retrieve market data for the given time period and interval
    # 
    # Returns:
    #   prices_df: Date, Open, High, Low, Close, Volume, Symbol 
    """    
    prices = {}
    
    # Retrieve ticker data from yfinance
    ticker_objs = get_tickers_from_yfinance(tickers)
    
    # Get historical price data for each ticker
    for symbol, ticker_obj in ticker_objs.items():
        prices[symbol] = ticker_obj.history(start=start, end=end, actions=False)
    
    cadence = BUSINESS_CADENCE_MAP[interval]
    
    prices_df = pd.DataFrame()
    
    # Add date index and symbol column to each dataframe
    for symbol, data in prices.items(): 
        data.index = pd.to_datetime(data.index).date
        data.index.name = 'Date'
        data.index = pd.to_datetime(data.index)
        data = data.set_index(data.index)
        
        data = data.asfreq(cadence)
        data['Symbol'] = symbol
        prices_df = pd.concat([prices_df, data], ignore_index=False)
    
    return prices_df

def get_current_price(tickers: list) -> pd.DataFrame:
    """ 
    Given list of tickers, return current/realtime price data
    
    Returns:
        current_prices_df: Symbol, Current Price
    """
    current_prices = []
    
    ticker_objs = get_tickers_from_yfinance(tickers)
    for symbol, obj in ticker_objs.items():
        try: 
            current_price = obj.info['currentPrice']
        except KeyError:
            current_price = obj.info['dayHigh']
        current_prices.append({
            'Symbol': symbol,
            'Current Price': current_price
        })
                        
    return pd.DataFrame(current_prices)
    
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
        get_historical_prices(tickers, start=start_date, interval=interval)
                
    # TODO: Pull out pct_ change to external function                
    # Add percent change column to each dataframe
    if pct_change:
        data_type = "Close" if close else "Open"
        for symbol, data in raw_price_data.items():
            raw_pct_change = data[data_type].pct_change() * 100
            raw_price_data[symbol]['Percent Change'] = \
                round(raw_pct_change, 2)
        
    return raw_price_data

# symbols = ['MSFT', 'AAPL', 'meta']

# ticker_info = get_tickers_from_yfinance(symbols)

# print(ticker_info)

# prices = get_historical_prices(symbols, interval="daily")
# prices = get_current_price(symbols)
# print_full(prices)


# a = yf.Ticker('QQQ')

# for k, v in a.info.items():
#     print("{}: {}".format(k, v))
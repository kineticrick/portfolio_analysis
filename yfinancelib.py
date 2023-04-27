#!/usr/bin/env python3

import pandas as pd
import yfinance as yf
from datetime import date
from dateutil.relativedelta import relativedelta

def print_full(df):
    """
    Prints the entirety of a PD dataframe, not just the shortened version
    """
    pd.set_option('display.max_rows', len(df))
    pd.set_option('display.max_columns', len(df.columns.values))
    print(df)
    pd.reset_option('display.max_rows')
    pd.reset_option('display.max_columns')

# def get_info(tickers): 
#     assert(isinstance(tickers, list))
    
#     ticker_str = " ".join(tickers)
    
#     ticker_info = {} 
#     if len(tickers) == 1: 
#         ticker = yf.Ticker(ticker_str)
#         symbol = ticker.info['symbol']
#         ticker_info[symbol] = ticker.info
#     elif len(tickers) > 1: 
#         tickers = yf.Tickers(ticker_str)
#         for obj in tickers.tickers: 
#             symbol = obj.info['symbol']
#             ticker_info[symbol] = obj.info
    
#     return ticker_info

# def get_dividend_yield(tickers): 
#     div_yields = {}
#     for symbol, info in get_info(tickers).items(): 
#         div_yields[symbol] = info['dividendYield']
    
#     return div_yields

# def show_all_avail_keys(): 
#     info = get_info(["aapl"])   
#     data = info['AAPL']
#     sorted_pairs = sorted(data.items())
#     for k, v in sorted_pairs: 
#         print(k, v)
    
# For any given ticker, retrieve market data for the given time period
# Returns close data (as opposed to open, high, low) by default
def get_price_data(tickers, period=None, interval=None, 
                   start=None, end=None, close=True):
    assert(isinstance(tickers, list))
    
    ticker_str = " ".join(tickers)
    
    ticker_info = {} 
    if len(tickers) == 1: 
        ticker = yf.Ticker(ticker_str)
        symbol = ticker.info['symbol']
        ticker_info[symbol] = ticker.history(
            period=period, interval=interval, start=start, end=end)
    elif len(tickers) > 1:
        tickers = yf.Tickers(ticker_str)
        for sym,obj in tickers.tickers.items(): 
            symbol = obj.info['symbol']
            ticker_info[symbol] = obj.history(
                period=period, interval=interval, start=start, end=end)
    
    # Retrieve open or close data only (and keep as dataframe)
    for symbol, data in ticker_info.items():
        if close: 
            ticker_info[symbol] = data['Close'].to_frame()
        else: 
            ticker_info[symbol] = data['Open'].to_frame()

    return ticker_info
    
# For the ticker, unit and length specified, retrieve summary returns 
# For instance, if unit is "months" and length is 3, returns the closing price
# for each of the last 3 months
# Currently defaults to daily data
# TODO: Add quaterly functionality
def get_summary_returns(tickers, unit="months", length=3, 
                        interval="daily", close=True):
    interval_map = {'daily': '1d', 'weekly': '1wk', 'monthly': '1mo',
                    'quarterly': '3mo', 'yearly': '1y'}
    start_date = get_dates_from_desc(unit, length)
    raw_price_data = get_price_data(tickers, interval=interval_map[interval],
                                    start=start_date, close=close)
    
    # Add percent change column to each dataframe
    data_type = "Close" if close else "Open"
    for symbol, data in raw_price_data.items():
        raw_price_data[symbol]['Percent Change'] = \
            data[data_type].pct_change()
        
    return raw_price_data

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
    
# For the interval and lengths specified, retrieve returns for each ticker
# def get_returns(tickers, period="1mo", interval="1d", 
#                 start=None, end=None):
    # assert(isinstance(tickers, list))
    
    # ticker_str = " ".join(tickers)
    
    # ticker_info = {} 
    # if len(tickers) == 1: 
    #     ticker = yf.Ticker(ticker_str)
    #     symbol = ticker.info['symbol']
    #     ticker_info[symbol] = ticker.history(
    #         period=period, interval=interval, start=start, end=end)
    # elif len(tickers) > 1:
    #     tickers = yf.Tickers(ticker_str)
    #     for sym,obj in tickers.tickers.items(): 
    #         symbol = obj.info['symbol']
    #         ticker_info[symbol] = obj.history(
    #             period=period, interval=interval, start=start, end=end)
    
    # # Retrieve close data only
    # for symbol, data in ticker_info.items():
    #     # print(type(data['Close']))
        # ticker_info[symbol] = data['Close'].pct_change()

    # return ticker_info


# tickers = ['MSFT', 'KO', 'DIS', 'REGN']
# print(get_price_data(tickers))    

# tickers = ['LDOS', 'V', 'PEP', 'STZ', 'KO', 'EQIX', 'MS', 'MGP', 'ASML', 
#            'KBH', 'HD', 'DRE', 'PHM', 'PEAK', 'MA']
# # print(get_dividend_yield(tickers))

# print(show_all_avail_keys())

# msft = yf.Ticker("AAPL")

# price_info = msft.history("6mo")
# meta = msft.history_metadata

# for k, v in meta.items(): 
#     print(k, v)

# print(msft.history_metadata)

# print(price_info)

# hist = msft.history(period="1mo")
# print(hist)

# print(msft.balance_sheet)

# print(get_dates_from_desc("years", 5))

        # ticker_info[symbol] = data['Close']
out = get_summary_returns(["MSFT", "KO", "DIS", "REGN"], 
                          unit="week", length=2, 
                          interval="daily", close=True)

for k, v in out.items():
    print(k)
    print_full(v)
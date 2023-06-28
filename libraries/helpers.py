#!/usr/bin/env python 
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import decimal
import math
import numpy as np
import pandas as pd

from collections import defaultdict
from libraries.dbcfg import *
from libraries.pandas_helpers import print_full, mysql_to_df
from libraries.sql import *
from libraries.yfinancelib import get_historical_prices, get_current_price
from libraries.vars import (NON_QUANTITY_ASSET_EVENTS, ASSET_EVENTS, 
                            MASTER_LOG_COLUMNS, CADENCE_MAP, 
                            BUSINESS_CADENCE_MAP)
from pandas.tseries.offsets import BDay

def build_master_log(symbols: list=[]) -> pd.DataFrame:
    """
    For each ASSET_EVENT, retrieve log of each event as a dataframe, then 
    merge each into a sorted master log

    If symbols are provided, only retrieve logs for those symbols

    Returns:
        pd.DataFrame: Single, chronologically sorted, master log of all events,
        across all assets 
    """
    # Master log of all events

    master_log_df = pd.DataFrame(columns=MASTER_LOG_COLUMNS)
    
    symbols_clause = \
        "(" + ", ".join([f"'{symbol}'" for symbol in symbols]) + ")"
    
    symbols_str = " symbol IN " + symbols_clause if len(symbols) > 0 else ""
                #    "(" + ", ".join([f"'{symbol}'" for symbol in symbols]) + ")"
                # ) if len(symbols) > 0 else ""

    # Retrieve log of each event as a dataframe, then 
    # merge each into a sorted master log
    for event in ASSET_EVENTS:
        query = globals()[f"master_log_{event}s_query"]
        if len(symbols) > 0: 
            if "WHERE" in query:
                query += " AND "
            else:
                query += " WHERE "
            query += symbols_str
            if event == 'acquisition': 
                query += ' OR acquirer IN ' + symbols_clause

        columns = globals()[f"master_log_{event}s_columns"]

        event_log_df = mysql_to_df(query, columns, dbcfg)
        master_log_df = pd.concat([master_log_df, event_log_df], ignore_index=True)

    # Acquisition events are stored in the master log as two separate events,
    # 'acquisition-target' and 'acquisition-acquirer'.  This allows each party to be 
    # independently and bidirectionally tied to the acquisition
    master_log_df['Action'] = master_log_df['Action'].replace('acquisition', 'acquisition-target')
    acquisition_acquirer_events = []
    
    # Swap "symbol" and "acquirer" columns for acquisition-acquirer events
    # This creates a complementary entry for the "other side" of the acquisition
    for _, acq_event in \
        master_log_df[master_log_df['Action'] == 'acquisition-target'].iterrows():
            acquisition_acquirer_events.append({
                'Date': acq_event['Date'],
                'Symbol': acq_event['Acquirer'],
                'Action': 'acquisition-acquirer',
                'Multiplier': acq_event['Multiplier'],
                'Target': acq_event['Symbol'],
            })
            
    # Merge into master log
    acquisition_acquirer_events_df = pd.DataFrame(acquisition_acquirer_events)
    master_log_df = pd.concat([master_log_df, acquisition_acquirer_events_df], ignore_index=True)

    # If specific symbols are provided, filter master log to only include those symbols
    # This is done because if you query just an acquisition-acquirer symbol, but not the 
    # acquisition-target, you'll still get the target in the log (since both are pulled from the 
    # 'acquisitions' table as part of the same row)
    if len(symbols) > 0:
        master_log_df = master_log_df[master_log_df['Symbol'].isin(symbols)]

    if len(symbols) > 0:
        # Sort by symbol, then date if specific symbols are provided
        sort_clause = ['Symbol', 'Date']
    else:
        # Sort by date, then multiplier if all assets retrieved
        sort_clause = ['Date', 'Multiplier']
    
    master_log_df = master_log_df.sort_values(by=sort_clause, 
                                              ascending=True,
                                              ignore_index=True)

    return master_log_df

def gen_hist_quantities(asset_event_log_df: pd.DataFrame, 
                        cadence: str=str, 
                        expand_chronology: bool=True) -> pd.DataFrame:
    """ 
    Based on log of asset events (buy, sell, split, etc) for a single asset,
    build a dataframe of historical quantities of that asset, on the 
    cadence given (daily, weekly, monthly, quaterly, yearly). 
    
    If expand_chronology is True, then the dataframe will include all dates.
    If False, then only dates with a quantity change will be included.
    
    Returns: quantities_df
        Date, Symbol, Action, Quantity (net)
        2019-01-01, MSFT, buy, 100
        2019-06-12, MSFT, sell, 50
    """
    #TODO: Ensure only one symbol is passed in
    
    # Remove non-quantity events, like dividend 
    # ('~' is the bitwise NOT operator)
    asset_event_log_df = asset_event_log_df[
        ~asset_event_log_df['Action'].isin(NON_QUANTITY_ASSET_EVENTS)]
    
    asset_event_log_df = \
        asset_event_log_df.sort_values(by=['Date'], ascending=True,)
        
    # Process each event and depending on the action, update the total quantity
    # all_events = []
    # Indexed by date to ensure that we only have one row per date
    all_events = defaultdict(dict)
    total_quantity = 0
    for _, event in asset_event_log_df.iterrows():
        date = event['Date']
        symbol = event['Symbol']

        all_events[date]['Date'] = date
        all_events[date]['Symbol'] = symbol
        
        action = event['Action']
        quantity = event['Quantity']
        multiplier = event['Multiplier']
        
        match action:
            case 'buy':
                total_quantity += quantity
                
            case 'sell':
                total_quantity -= quantity
                
            case 'split':
                total_quantity *= multiplier
                
            case 'acquisition-target':
                total_quantity = 0
                
            case 'acquisition-acquirer':
                # Get the quantity of the acquisition target asset on the date of the acquisition
                target = [event['Target']]
                day_before = date - BDay(1)

                target_prior_quantity_df = \
                    get_asset_quantity_by_date(target, day_before.strftime('%Y-%m-%d'))

                target_prior_quantity = decimal.Decimal(target_prior_quantity_df['Quantity'])

                # Add the quantity of the target asset * multiplier to the acquirer's total
                target_prior_quantity *= multiplier
                target_prior_quantity = math.floor(target_prior_quantity)
                total_quantity += target_prior_quantity
    
        all_events[date]['Quantity'] = total_quantity

    all_events = list(all_events.values())        
    quantities_df = pd.DataFrame(all_events)
    
    # Set date as DateTimeIndex
    quantities_df['Date'] = pd.to_datetime(quantities_df['Date'])

    if expand_chronology:
        first_date = quantities_df['Date'].iloc[0]

        if quantities_df['Quantity'].iloc[-1] == 0: 
            # If there are no more shares held, use the last date held 
            last_date = quantities_df['Date'].iloc[-1]

        else:
            # If there are still shares held, use today as the last date
            last_date = pd.to_datetime('today').date()

        # Advance the last date to the end of the last date's period, to capture
        # all actions
        last_period = pd.Period(last_date, freq=CADENCE_MAP[cadence])
        last_date = last_period.end_time.date()

        # Fill in dataframe with every date in the range
        date_range = pd.date_range(start=first_date, end=last_date, 
                                freq='D')

        quantities_df = quantities_df.set_index('Date').reindex(date_range)

        # Fill in missing values with previous value
        # IE Set quantity to last/current, as of that date
        quantities_df['Quantity'] = quantities_df['Quantity'].fillna(method='ffill')
        quantities_df['Symbol'] = quantities_df['Symbol'].fillna(method='ffill')
        
        # Downsample to specified cadence
        quantities_df = quantities_df.asfreq(BUSINESS_CADENCE_MAP[cadence])
        
    if "Date" in quantities_df.columns: 
        quantities_df = quantities_df.set_index('Date')

    return quantities_df

def gen_hist_quantities_mult(assets_event_log_df: pd.DataFrame, 
                             cadence: str=str, 
                             expand_chronology: bool=True) -> pd.DataFrame:
    """
    Given an event log of multiple assets, generate a dataframe of historical
    quantities of each asset, on the cadence given (daily, weekly, monthly, etc)
    If only need to process a single asset, use gen_hist_quantities()
    
    If expand_chronology is True, then the dataframe will include all dates.
    If False, then only dates with a quantity change will be included.
    
    Returns: quantities_df 
    Date, Symbol, Action, Quantity (net)
    2019-01-01, MSFT, buy, 100
    2019-06-12, MSFT, sell, 50
    2020-02-07, DIS, buy, 75
    2020-08-22, DIS, buy, 20
    """
    
    # Get list of unique symbols
    symbols = assets_event_log_df['Symbol'].unique()

    quantities_df = pd.DataFrame()
    # Get historical quantities for each symbol
    for symbol in symbols:
        symbol_event_log_df = assets_event_log_df[
            assets_event_log_df['Symbol'] == symbol]
        symbol_quantities_df = gen_hist_quantities(symbol_event_log_df, 
                                                   cadence=cadence,
                                                   expand_chronology=expand_chronology)
        quantities_df = pd.concat([quantities_df, symbol_quantities_df], 
                                  )
    return quantities_df

def get_asset_quantity_by_date(symbols: list, date: str) -> pd.DataFrame:
    """
    Get quantity of each asset in portfolio, as of a given date
    """
    #TODO: Assert date format
    
    asset_events_log = build_master_log(symbols)
    hist_quantities_df = gen_hist_quantities_mult(asset_events_log, 'daily')
    
    return hist_quantities_df.loc[date]

def gen_assets_historical_value(symbols: list=[], 
                                cadence: str='quarterly',
                                start_date: str=None) -> pd.DataFrame:
    """ 
    Provide lifetime value of asset within portfolio over time
    Takes quantity of shares, and asset price at that time, to calculate
    Defaults to daily cadence, unless specified 
    
    Can be used to generate historical daily value of every asset every owned 
    (and, by extension, full portfolio)
    
    Returns: merged_df -> 
    Date, Symbol, Quantity, Close, Value (Quantity * Close)
    2019-01-01, MSFT, 100, 67, 6700
    2019-01-02, MSFT, 100, 68, 6800
    """
    assert(cadence in CADENCE_MAP.keys())
    assert(type(symbols) == list)
    
    # Get master event log for asset 
    assets_event_log_df = build_master_log(symbols)

    # Get historical share quantities of assets
    quantities_df = gen_hist_quantities_mult(assets_event_log_df, 
                                              cadence=cadence)

    if start_date is not None:
        start_date = pd.to_datetime(start_date)
        quantities_df = \
            quantities_df[quantities_df.index >= start_date]

    sorted_quantities_df = \
        quantities_df.sort_index(ascending=True)
            
    # Get first and last dates to query historical prices for all assets
    # Once we have superset of all dates for all assets, can pull subset
    # for just the dates we owned the asset. Much faster to pull all prices
    # with a single query, than to query for each asset with specific dates
    first_date = sorted_quantities_df.index[0]
    last_date = sorted_quantities_df.index[-1]

    # Only use the symbols found in our transactions data
    # This should be identical to those passed in, but just in case
    returned_symbols = list(quantities_df['Symbol'].unique())
    
    # Get historical prices of assets
    prices_df = get_historical_prices(tickers=returned_symbols, 
                                start=first_date, end=last_date,
                                interval=cadence)
    

    # Standardize quantities and prices dataframes
    quantities_df = quantities_df.reset_index()
    prices_df = prices_df.reset_index()
    quantities_df = quantities_df.rename(columns={'index': 'Date'})
    prices_df = prices_df.rename(columns={'index': 'Date'})
    
    # Only keep needed columns from price data
    prices_df = prices_df[['Date', 'Symbol', 'Close']]

    # Merge quantities and prices
    merged_df = \
        quantities_df.merge(prices_df, 
                            on=['Date','Symbol'], how='left')
        
    # Calculate value of asset at each date
    merged_df['Value'] = merged_df['Quantity'] * merged_df['Close']
    
    # Round to 2 decimal places
    merged_df = merged_df.round(2)
    
    # Remove NaN rows
    merged_df = merged_df.dropna(how='any')
    
    return merged_df

def get_portfolio_summary() -> pd.DataFrame:
    """ 
    Retrieve summary table of entire portfolio

    Returns: 
        portfolio_summary_df: Symbol, Name, Quantity, Cost Basis, 
                              First Purchase Date, Last Purchase Date, 
                              Total Dividend, Dividend Yield 
    """
    
    portfolio_summary_df = \
        mysql_to_df(read_summary_table_query, read_summary_table_columns, dbcfg)
    
    return portfolio_summary_df
    
    
def get_portfolio_current_value() -> tuple[pd.DataFrame, float]:
    """ 
    Retrieve total value of entire portfolio at current time
    Returns:
        summary_df: (See get_portfolio_summary()) + Current Price, Current Value
        total_value: Total value of portfolio, as float
    """
    
    summary_df = get_portfolio_summary()
    symbols = list(summary_df['Symbol'].unique())
    
    current_prices = get_current_price(symbols)

    summary_df = summary_df.merge(current_prices, on='Symbol', how='left')
    summary_df['Current Value'] = summary_df['Quantity'] * summary_df['Current Price']

    total_value = summary_df['Current Value'].sum()
    
    return (summary_df, total_value)


dup_symbols = [
    'SNAP',
    'META',
    'HD',
]

symbols = [
    'MSFT', 
    'V',
           'META', 
           'NFLX', 'DIS','AMZN',
           ]

# TODO: BUILDIN ERROR HANDLING
# Symbols that don't exist
# Symbols that don't have any data

# out = build_master_log()
# out = gen_assets_historical_value(['msft', 'WEED', 'MGP', 'DRE'], cadence='quarterly')
# out = gen_assets_historical_value(cadence='daily')
# print_full(out)
# out.to_csv('daily_asset_values.csv', index=False)


# csv_df.to_csv('test.csv', index=False)

# daily_values_cf = pd.read_csv('daily_asset_values.csv')
# num_symbols = len(daily_values_cf['Symbol'].unique())

# global_daily_values = daily_values_cf.groupby('Date')['Value'].sum()
# print(isinstance(global_daily_values, pd.Series))
# print(isinstance(daily_values_cf, pd.DataFrame))
# print_full(global_daily_values)

# import plotly.express as px 
# fig = px.line(global_daily_values, x=global_daily_values.index, y=global_daily_values.values)
# fig.show()

# summ_df = get_portfolio_summary()
# print_full(summ_df)

# val_df, total_val = get_portfolio_current_value()

# print_full(val_df)
# print(total_val)

# out = build_master_log(['DRE', 'PLD', 'MGP', 'VICI'])
# print_full(out)

# out = gen_assets_historical_value(['MSFT', 'META'], cadence='weekly', start_date='2023-05-01')
# print_full(out)

# symbols = ['VICI','MGP']

# logs = build_master_log(symbols)
# print_full(logs)
# out = gen_hist_quantities_mult(logs, cadence='daily', expand_chronology=False)
# print_full(out)

# out = get_asset_quantity_by_date(symbols, '2020-08-11')

# print_full(out)


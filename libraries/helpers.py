#!/usr/bin/env python 
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd

from libraries.dbcfg import *
from libraries.pandas_helpers import * 
from libraries.sql import *
from libraries.yfinancelib import get_price_data
from libraries.vars import (QUANTITY_ASSET_EVENTS, ASSET_EVENTS, 
                            MASTER_LOG_COLUMNS, CADENCE_MAP, 
                            BUSINESS_CADENCE_MAP)

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
    
    symbols_str = (" symbol IN "
                   "(" + ", ".join([f"'{symbol}'" for symbol in symbols]) + ")"
                ) if len(symbols) > 0 else ""

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
        columns = globals()[f"master_log_{event}s_columns"]
        
        event_log_df = mysql_to_df(query, columns, dbcfg)
        master_log_df = pd.concat([master_log_df, event_log_df], ignore_index=True)

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

def gen_historical_quantities(asset_event_log_df: pd.DataFrame, 
                              cadence: str=str) -> pd.DataFrame:
    """ 
    Based on log of asset events (buy, sell, split, etc) for a single asset,
    build a dataframe of historical quantities of that asset, on the 
    cadence given (daily, weekly, monthly, quaterly, yearly)
    
    Returns: quantities_df
        Date, Symbol, Action, Quantity 
    """
    #TODO: Ensure only one symbol is passed in
    
    # Only use quantity-affecting events (ie buy, sell, split, acquisition)
    asset_event_log_df = asset_event_log_df[
        asset_event_log_df['Action'].isin(QUANTITY_ASSET_EVENTS)]
    
    asset_event_log_df = \
        asset_event_log_df.sort_values(by=['Date'], ascending=True,)
        
    # Process each event and depending on the action, update the total quantity
    all_events = []
    total_quantity = 0
    for _, event in asset_event_log_df.iterrows():
        date = event['Date']
        symbol = event['Symbol']
        action = event['Action']
        quantity = event['Quantity']
        multiplier = event['Multiplier']
        
        event_dict = {'date': date, 
                      'symbol': symbol, 
                      }
        
        match action:
            case 'buy':
                total_quantity += quantity
                
            case 'sell':
                total_quantity -= quantity
                
            case 'split':
                total_quantity *= multiplier
                
            case 'acquisition':
                total_quantity = 0
    
        event_dict['quantity'] = total_quantity
        all_events.append(event_dict)
        
    quantities_df = pd.DataFrame(all_events)
    
    # Set date as DateTimeIndex
    quantities_df['date'] = pd.to_datetime(quantities_df['date'])
    first_date = quantities_df['date'].iloc[0]

    if quantities_df['quantity'].iloc[-1] == 0: 
        # If there are no more shares held, use the last date held 
        last_date = quantities_df['date'].iloc[-1]

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
    quantities_df = quantities_df.set_index('date').reindex(date_range)
    
    # Fill in missing values with previous value
    # IE Set quantity to last/current, as of that date
    quantities_df['quantity'] = quantities_df['quantity'].fillna(method='ffill')
    quantities_df['symbol'] = quantities_df['symbol'].fillna(method='ffill')
    
    # Downsample to specified cadence
    quantities_df = quantities_df.asfreq(BUSINESS_CADENCE_MAP[cadence])
    
    return quantities_df

def gen_asset_historical_value(symbol: str, cadence: str=None) -> pd.DataFrame:
    """ 
    Provide lifetime value of asset within portfolio over time
    Takes quantity of shares, and asset price at that time, to calculate
    Defaults to daily cadence, unless specified 
    
    Returns: merged_df -> Date, Symbol, Quantity, Close, Value (Quantity * Close)
    """
    
    #TODO: Process multiple symbols at once
    
    # Get master event log for asset 
    asset_event_log_df = build_master_log(symbols=[symbol])
    
    # Get historical quantities of asset
    quantities_df = gen_historical_quantities(asset_event_log_df, 
                                              cadence=cadence)

    # Get first and last dates for asset holding
    first_date = quantities_df.index[0]
    last_date = quantities_df.index[-1]
    
    # Get historical prices of asset
    prices_df = get_price_data(tickers=[symbol], 
                                start=first_date, end=last_date,
                                interval=cadence)
    prices_df = prices_df[symbol]
    prices_df = prices_df['Close']
    
    # Merge quantities and prices
    merged_df = quantities_df.merge(prices_df, left_index=True, right_index=True)
  
    # Calculate value of asset at each date
    merged_df['Value'] = merged_df['quantity'] * merged_df['Close']
    
    # Remove NaN rows
    merged_df = merged_df.dropna(how='any')
    
    return merged_df
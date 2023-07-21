#!/usr/bin/env python

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

import pandas as pd
import numpy as np
from pandas.tseries.offsets import DateOffset
from libraries.pandas_helpers import print_full
from libraries.helpers import get_portfolio_current_value

from libraries.HistoryHandler import (PortfolioHistoryHandler, 
                                      AssetHistoryHandler)

class DashboardHandler:
    def __init__(self) -> None:
        # Set milestones
        self.performance_milestones = [
            ('1d', 1), 
            ('1w', 7),
            ('1m', 30),
            ('3m', 90),
            ('6m', 180),
            ('1y', 365),
            ('2y', 730),
            ('3y', 1095),
            ('5y', 1825),
            # Lifetime will also be added when milestones are generated
        ]
        
        # Get and Set current portfolio value
        portfolio_summary_df, portfolio_value = get_portfolio_current_value()
        self.current_portfolio_summary_df = portfolio_summary_df
        self.current_portfolio_value = portfolio_value
    
        # Get and Set portfolio history
        ph = PortfolioHistoryHandler()
        self.portfolio_history_df = ph.get_history()

        # Index by date - can be done here since portfolio history 
        # has a single set of unique dates (no duplicates)
        self.portfolio_history_df['Date'] = \
            pd.to_datetime(self.portfolio_history_df['Date'])
        self.portfolio_history_df = self.portfolio_history_df.set_index('Date')
        
        # Add current value to portfolio history
        self.portfolio_history_df.loc[pd.to_datetime('today')] = \
            self.current_portfolio_value
        
        # Get and set assets history
        ah = AssetHistoryHandler()
        self.assets_history_df = ah.get_history()

        # Get and set portfolio milestones
        self.portfolio_milestones = self.get_portfolio_milestones()
        
        # Get and set asset milestones
        self.asset_milestones = self.get_asset_milestones()
        
    def _gen_performance_milestones(self, history_df: pd.DataFrame, current_value: float,
                                    current_price: float=None,  
                                    milestones: list=[]) -> pd.DataFrame: 
        """ 
        Given a history dataframe, current value, and milestone dates, generate 
        a dataframe containing the values at each milestone date, and percentage return
        
        History_df: Must be indexed by date, and contain a column 'Value'
        Milestones: List of (interval, days) tuples
        
        Returns: milestones_df (pd.DataFrame)
            Date, Symbol, Interval, Value, Percent Return
            2023-06-29, Symbol, 1d, 123.45, 0.5 
            
        """
        
        # If milestones is empty, use default milestones
        milestones = milestones if milestones else self.performance_milestones
        
        # Run milestone calculations
        milestone_values = []
        
        # Populate each milestone date with the value of the portfolio on that date
        for (interval, days) in milestones:
            offset = DateOffset(days=days)
            milestone_date = pd.to_datetime('today') - offset
            milestone_date = milestone_date.strftime('%Y-%m-%d')
            
            try: 
                milestone_value = history_df.loc[milestone_date]['Value']
            except KeyError:
                continue
            symbol = history_df.loc[milestone_date]['Symbol'] \
                if 'Symbol' in history_df else "PORTFOLIO"
            
            milestone_dict = {
                'Date': milestone_date,
                'Symbol': symbol,
                'Interval': interval,
                'Current Value': current_value,
                'Value': milestone_value,
            }
            
            if current_price is not None:
                milestone_dict['Current Price'] = current_price
            
            if 'ClosingPrice' in history_df:
                milestone_price = history_df.loc[milestone_date]['ClosingPrice']
                milestone_dict['Price'] = milestone_price
            
            milestone_values.append(milestone_dict)
        
        # Get lifetime return
        earliest_date = history_df.index.min().date().strftime('%Y-%m-%d')
        earliest_value = history_df.loc[earliest_date]['Value']
        milestone_dict = {
                'Date': earliest_date,
                'Symbol': symbol,
                'Interval': 'Lifetime',
                'Value': earliest_value,
        }
        if 'ClosingPrice' in history_df:
            milestone_price = history_df.loc[earliest_date]['ClosingPrice']
            milestone_dict['Price'] = milestone_price
        milestone_values.append(milestone_dict)
        
        milestones_df = pd.DataFrame(milestone_values)
        milestones_df['Value'] = milestones_df['Value'].astype(float)
        
        # Generate % improvement from each milestone to current value
        milestones_df['Value % Return'] = round(
            (current_value - milestones_df['Value']) \
                / milestones_df['Value'] * 100, 2)

        if current_price is not None:
            
            milestones_df['Price'] = milestones_df['Price'].astype(float)
            # Generate % improvement from each milestone to current value
            milestones_df['Price % Return'] = round(
                (current_price - milestones_df['Price']) \
                    / milestones_df['Price'] * 100, 2)
        
        return milestones_df
    
    def get_portfolio_milestones(self) -> pd.DataFrame:
        """
        Get value of portfolio at each milestone
        
        Returns: milestones_df (pd.DataFrame)
            Date, Interval, Value, Percent Return
            2023-06-29, 1d, 123.45, 0.5 
        """
        milestones_df = self._gen_performance_milestones(
            self.portfolio_history_df, self.current_portfolio_value)
        
        return milestones_df
        
    def get_asset_milestones(self, symbols: list=[]) -> pd.DataFrame:
        """
        For symbols given, get value of asset at each milestone
        
        If symbols are not provided, use all symbols in current portfolio
        """
        
        if not symbols:
            symbols = list(self.current_portfolio_summary_df['Symbol'].unique())
            
        milestones_df = pd.DataFrame()
        for symbol in symbols: 
            # For each symbol, get the current value and history
            current_price = self.current_portfolio_summary_df.loc[
                self.current_portfolio_summary_df['Symbol'] == symbol]['Current Price'].values[0]
            current_value = self.current_portfolio_summary_df.loc[
                self.current_portfolio_summary_df['Symbol'] == symbol]['Current Value'].values[0]
            history_df = self.assets_history_df.loc[self.assets_history_df['Symbol'] == symbol]
            
            # Index date for specific asset, since it's now a unique set of dates
            pd.set_option('mode.chained_assignment',None)
            history_df['Date'] = pd.to_datetime(history_df['Date'])
            history_df = history_df.set_index('Date')
            
            # Generate milestones for each asset
            asset_milestones_df = \
                self._gen_performance_milestones(history_df, current_value, 
                                                 current_price=current_price)
            
            milestones_df = pd.concat([milestones_df, asset_milestones_df])
        
        return milestones_df
    
    #TODO: Implement this for all assets over history - and add N (ie top 5, 10)
    def get_ranked_assets(self,  interval: str, price_or_value: str='price',
                          ascending: bool=False, count: int=None) -> pd.DataFrame:
        """
        Given time interval, rank assets currently in the portfolio by their return
        """
        all_intervals, _ = zip(*self.performance_milestones)
        
        assert(interval in all_intervals)
        assert(price_or_value in ['price', 'value'])
         
        # Get milestones for the given interval
        ranked_assets_df = self.asset_milestones.loc[
            self.asset_milestones['Interval'] == interval]
        
        rank_column = 'Price % Return' if price_or_value == 'price' \
            else 'Value % Return'
        
        ranked_assets_df = ranked_assets_df.sort_values(
            by=rank_column, ascending=ascending)
        
        if count:
            ranked_assets_df = ranked_assets_df.head(count)
        
        return ranked_assets_df
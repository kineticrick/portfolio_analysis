#!/usr/bin/env python

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import pandas as pd
from pandas.tseries.offsets import DateOffset
from libraries.pandas_helpers import print_full
from libraries.helpers import (get_portfolio_current_value, add_asset_info)

from libraries.HistoryHandlers import AssetHistoryHandler
from libraries.HistoryHandlers import AssetHypotheticalHistoryHandler
from libraries.HistoryHandlers import PortfolioHistoryHandler
from libraries.HistoryHandlers import SectorHistoryHandler

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

        ######## ASSETS ########
        ah = AssetHistoryHandler()
        
        # Get and Set current portfolio value
        # NOTE: Doing this here because it's needed for assets summary, 
        # though it should be in the "PORTFOLIO" section
        portfolio_summary_df, portfolio_value = get_portfolio_current_value()
        self.current_portfolio_summary_df = portfolio_summary_df
        self.current_portfolio_value = portfolio_value
        
        # Get and set assets history
        self.assets_history_df = ah.history_df
        portfolio_symbols = self.current_portfolio_summary_df['Symbol'].tolist()
        self.portfolio_assets_history_df = self.assets_history_df.loc[
            self.assets_history_df['Symbol'].isin(portfolio_symbols)]

        # Get and set asset milestones
        self.asset_milestones = self.get_asset_milestones()

        # Get and set asset summary
        self.assets_summary_df = self._gen_assets_summary()
  
        ####### PORTFOLIO ########
        ph = PortfolioHistoryHandler(assets_history_df = self.assets_history_df)
        
        # Get and Set portfolio history
        self.portfolio_history_df = ph.history_df

        # Index by date - can be done here since portfolio history 
        # has a single set of unique dates (no duplicates)
        self.portfolio_history_df['Date'] = \
            pd.to_datetime(self.portfolio_history_df['Date'])
        self.portfolio_history_df = self.portfolio_history_df.set_index('Date')
        
        # Add current value to portfolio history
        self.portfolio_history_df.loc[pd.to_datetime('today')] = \
            self.current_portfolio_value

        # Get and set portfolio milestones
        self.portfolio_milestones = self.get_portfolio_milestones()
  
        ####### HYPOTHETICALS #######

        # Get and set assets hypothetical history for all exited assets
        ahh = AssetHypotheticalHistoryHandler(
            assets_history_df=self.assets_history_df)
        
        self.assets_hypothetical_history_df = ahh.history_df

    #     # Split into actuals and hypotheticals, to make it possibly easier when needed
        self.exits_actuals_history_df = self.assets_hypothetical_history_df.loc[
            (self.assets_hypothetical_history_df['Owned'] == 'Actual')]
        self.exits_hypotheticals_history_df = self.assets_hypothetical_history_df.loc[
            (self.assets_hypothetical_history_df['Owned'] == 'Hypothetical')]

        ####### SECTORS #######
        
        # Get and set sectors values history
        sh = SectorHistoryHandler()
        self.sectors_history_df = sh.history_df
        self.sectors_summary_df = self._gen_sectors_summary()

        
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
    
    #TODO: Implement this for all assets over entire history - and add N (ie top 5, 10)
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
    
    def _gen_pct_change_cols(self, history_df: pd.DataFrame, 
                       column_names: list) -> pd.DataFrame:
        """
        Given a history dataframe with a single set of unique dates + symbol/sector/asset_type, 
        generate a column for % change
        """
        for column_name in column_names:
            history_df[column_name] = history_df[column_name].astype(float)
            history_df[column_name + ' % Change'] = \
                round((history_df[column_name] - history_df[column_name][0]) / 
                    history_df[column_name][0] * 100, 2)
        
        return history_df
    
    def _add_pct_change(self, history_df: pd.DataFrame, 
                       column_names: list, 
                       id_column: str="Symbol") -> pd.DataFrame:
        """
        Given a history dataframe with multiple symbols/sectors (and overlapping dates), 
        generate a column for % change for each symbol
        
        """
        master_df = pd.DataFrame()
        
        ids = list(history_df[id_column].unique())
        
        # Process a mini df of each symbol/sector/asset type and add to master
        for id in ids:
            id_df = history_df.loc[history_df[id_column] == id]
            id_df = id_df.sort_values(by='Date') \
                if 'Date' in id_df else id_df.sort_index()
            id_df = id_df.reset_index(drop=True)
            id_df = self._gen_pct_change_cols(id_df, column_names)
            master_df = pd.concat([master_df, id_df])

        return master_df
    
    def expand_history_df(self, history_df: pd.DataFrame, 
                          id_column: str="Symbol") -> pd.DataFrame:
        """ 
        Given a base history dataframe, containing historical quantities, prices and 
        values for multiple symbols or sectors (each with varying dates), add in the following info: 
            - Percent return for each period from the initial price (Price)
            AND/OR
            - Percent return for each period from the initial value (Value)
            AND/OR
            - Info on the asset (Company or Asset Name, Sector, Asset Type) [Assets/Symbols only]
            
        "id_column" can be "Symbol" [ie assets], "Sector" or "Asset Type"
            [IE etf, common stock, REIT]
            
        Columns added:
            [Assets]
            ClosingPrice % Change, Value % Change
            Name, Asset Type, Sector
            
            [Sectors] or [Asset Types]
            Value % Change
        """
        assert(id_column in ['Symbol', 'Sector', 'Asset Type'])
        
        metric_column_names = []
        if "ClosingPrice" in history_df:
            metric_column_names.append("ClosingPrice")

        if "Value" in history_df:
            metric_column_names.append("Value")

        history_df= self._add_pct_change(history_df, metric_column_names, id_column)
        if id_column == "Symbol":
            history_df = add_asset_info(history_df)
        
        return history_df
    
    def gen_historical_stats(self, history_df: pd.DataFrame, 
                             hypotheticals: bool=False) -> pd.DataFrame:
        """ 
        For each symbol (and its history) in history_df, generate the 
        following set of statistics
        
        History_df can be either actuals, or actuals + hypotheticals
        
        Default: 
            - Total/Lifetime Return (Return %, purchase -> current)
            - Max return %, purchase -> current
            - Average Return (Daily)
            - Annualized Return
            - Standard Deviation
            - Sharpe Ratio
            - Sortino Ratio
        Hypotheticals
            - Return %, exit -> current
            - Return %, purchase -> current
            - Max return %, exit -> current
            - Max return %, purchase -> current
        """
        
        # If we're dealing with hypotheticals, split into actuals and hypotheticals
        if hypotheticals and "Owned" in history_df: 
            actuals_df = history_df.loc[history_df['Owned'] == 'Actual']
            hypos_df = history_df.loc[history_df['Owned'] == 'Hypothetical']
        # Otherwise we're dealing with only actuals (a currently owned asset), 
        # so the entire history is actuals
        else: 
            actuals_df = history_df 
            
        stats_data = []
        symbols = list(actuals_df['Symbol'].unique())
        
        # For each symbol in the history dataframe, process the actuals as both/either
        # the entirety of the history (in which case we get only the default stats), or
        # as just the actuals, followed by the hypotheticals (which get their own set of
        # additional stats)
        for symbol in symbols: 
            # Get the actuals for the symbol, and sort by date
            symbol_actuals_df = actuals_df.loc[actuals_df['Symbol'] == symbol]
            symbol_actuals_df = symbol_actuals_df.sort_values(by='Date')
            symbol_actuals_df = symbol_actuals_df.reset_index(drop=True)
            
            # Get key milestone prices
            enter_price = symbol_actuals_df['ClosingPrice'].iloc[0]
            latest_actuals_price = symbol_actuals_df['ClosingPrice'].iloc[-1]
            max_actuals_price = symbol_actuals_df['ClosingPrice'].max()
            
            # Return from acquisition to last price during ownership
            # (if currently owned, this is now. If sold in the past, this is exit date)
            actuals_enter_to_latest = round(
                (latest_actuals_price - enter_price) / enter_price * 100, 2)
    
            # Return from acquisition to max price during ownership 
            actuals_enter_to_max = round(
                (max_actuals_price - enter_price) / enter_price * 100, 2)

            # Store in dict, to be later converted to dataframe
            stats_dict = {
                'Symbol': symbol,
                'Actuals Ret.(Enter/Latest)%': actuals_enter_to_latest,
                'Actuals Ret.(Enter/Max)%': actuals_enter_to_max,
            }
            
            #TODO: Add other stats, like stdDev, sharpe, etc

            # If we're dealing with hypotheticals, add in the hypotheticals stats
            if hypotheticals: 
                symbol_hypos_df = hypos_df.loc[hypos_df['Symbol'] == symbol]
                if symbol_hypos_df.empty:
                    continue
                
                symbol_hypos_df = symbol_hypos_df.sort_values(by='Date')
                symbol_hypos_df = symbol_hypos_df.reset_index(drop=True)
                
                exit_price = symbol_hypos_df['ClosingPrice'].iloc[0]
                latest_hypo_price = symbol_hypos_df['ClosingPrice'].iloc[-1]
                max_hypo_price = symbol_hypos_df['ClosingPrice'].max()

                # Return from acquisition to current price (which is end of 
                # hypothetical history, since it's unowned)
                hypos_enter_to_current = round(
                    (latest_hypo_price - enter_price) / enter_price * 100, 2)                
           
                # Return from sale to current price
                hypos_exit_to_current = round(
                    (latest_hypo_price - exit_price) / exit_price * 100, 2)
           
                # Return from acquisition to max price AFTER sale
                hypos_enter_to_max = round(
                    (max_hypo_price - enter_price) / enter_price * 100, 2)
           
                # Return from sale to max price AFTER sale
                hypos_exit_to_max = round(
                    (max_hypo_price - exit_price) / exit_price * 100, 2)

                # Store in dict
                stats_dict['Hypo Ret.(Enter/Current)%'] = \
                    hypos_enter_to_current
                stats_dict['Hypo Ret.(Exit/Current)%'] = \
                    hypos_exit_to_current
                stats_dict['Hypo Ret.(Enter/Max)%'] = \
                    hypos_enter_to_max
                stats_dict['Hypo Ret.(Exit/Max)%']= \
                    hypos_exit_to_max
                
            stats_data.append(stats_dict)
        
        stats_df = pd.DataFrame(stats_data)
        
        sort_col = 'Hypo Ret.(Exit/Current)%' \
            if hypotheticals else 'Actuals Ret.(Enter/Latest)%'
        stats_df = stats_df.sort_values(by=sort_col, ascending=False)
        stats_df = add_asset_info(stats_df)
        
        return stats_df
    

    def _gen_assets_summary(self) -> pd.DataFrame:
        """ 
        Builds a master summary of all assets in the portfolio, including all attributes
        listed in summary_cols and return_cols below
        """
        summary_cols = ['Symbol', 'Name', 'Sector','Asset Type', 'Quantity',
                        'First Purchase Date', 'Last Purchase Date', 'Cost Basis',
                        'Current Price', 'Current Value', '% Total Portfolio' , 
                        'Lifetime Return', 'Dividend Yield', 'Total Dividend', ]        
        returns_cols = ['1d', '1w', '1m', '3m', '6m', '1y', '2y', '3y', '5y']
        
        # Pivot the milestone returns for all assets into a dataframe with a 
        # single row per unique asset, with columns for each interval
        returns_df = self.asset_milestones 
        returns_df = returns_df.pivot(
            index='Symbol', columns='Interval', values='Price % Return')
        returns_df = returns_df[returns_cols]
        
        summary_df = self.current_portfolio_summary_df[summary_cols]
        
        assets_summary_df = pd.merge(summary_df, returns_df, on='Symbol')
        
        return assets_summary_df
    
    
    def _gen_sectors_summary(self) -> pd.DataFrame:
        """
        Generate a summary of all sectors in the portfolio, including the 
        following information
            - Sector Name
            - Cost Basis
            - Current Market Value
            - % of Total Portfolio
            - Lifetime Return (Sum Cost Basis vs Sum Market Value)
            - Avg Daily Return (Avg of all assets daily return)
            - Avg Dividends Yield (% - Avg of all assets dividend yield)
            - Total Dividends ($ - Sum of all assets dividends)
            - TODO: Milestone Returns (1d, 1w, 1m, 3m, 6m, 1y, 2y, 3y, 5y)

        Returns:
            sectors_summary_df: 
        """
        portfolio_summary_df = self.current_portfolio_summary_df
        sectors_summary_df = pd.DataFrame()
        
        # For Cost Basis, Current Value, Total Dividend, get sum grouped by sector
        sector_sum_cols = ['Cost Basis', 'Current Value', 'Total Dividend']
        sectors_summary_df = portfolio_summary_df.groupby('Sector')[sector_sum_cols].sum()
        sectors_summary_df = sectors_summary_df.reset_index()

        # For Dividend Yield, get mean grouped by sector
        sector_mean_cols = ['Dividend Yield']
        sectors_mean_df = portfolio_summary_df.groupby('Sector')[sector_mean_cols].mean()
        sectors_mean_df = sectors_mean_df.reset_index()
        sectors_summary_df = sectors_summary_df.merge(sectors_mean_df, on='Sector')

        # For % of Total Portfolio, divide current value by total portfolio value
        sectors_summary_df['% of Total Portfolio'] = \
            sectors_summary_df['Current Value'] / self.current_portfolio_value * 100

        # For Lifetime Return, get current value - cost basis / cost basis
        sectors_summary_df['Lifetime Return'] = \
            (sectors_summary_df['Current Value'] - sectors_summary_df['Cost Basis']) \
                / sectors_summary_df['Cost Basis'] * 100

        # For avg daily return, get latest daily return for each asset 
        # from sectors_history_df        
        latest_sectors_history_date = self.sectors_history_df['Date'].max()
        latest_sectors_history_df = self.sectors_history_df.loc[
            self.sectors_history_df['Date'] == latest_sectors_history_date] 
        latest_sectors_history_df = latest_sectors_history_df.reset_index(
            drop=True)
        latest_sectors_history_df = latest_sectors_history_df.drop(
            columns=['Date'])
        sectors_summary_df = sectors_summary_df.merge(latest_sectors_history_df, 
                                                      on='Sector', how='left')
        
        sectors_summary_df = sectors_summary_df.round(2)
        
        
        return sectors_summary_df
    
    
dh = DashboardHandler()

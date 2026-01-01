import os
import sys
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from libraries.db import dbcfg, MysqlDB
from libraries.db.sql import (create_portfolio_history_table_sql, 
                              insert_update_portfolio_history_sql, 
                              insert_ignore_portfolio_history_sql, 
                              read_portfolio_history_query, 
                              read_portfolio_history_columns)
from libraries.HistoryHandlers import BaseHistoryHandler, AssetHistoryHandler
from libraries.pandas_helpers import print_full, mysql_to_df

class PortfolioHistoryHandler(BaseHistoryHandler):
    create_history_table_sql = create_portfolio_history_table_sql
    
    def __init__(self, assets_history_df: pd.DataFrame=None) -> None:
        """ 
        Initialize object with updated portfolio history from DB, 
        which contains a total value of the entire portfolio (all assets)
        for each day of existence
       
        (Date, value)
        """
        self.assets_history_df = assets_history_df
        super().__init__()

    def set_history(self, start_date: str=None, overwrite: bool=False) -> pd.DataFrame:
        """
        Update DB with portfolio history info from start_date to today

        If overwrite is True, overwrite all existing history in DB with
        new derived history. Else, only add new history to DB (append-only)

        Args:
            start_date (str): Date to start history from (inclusive)

        Returns:
            pd.DataFrame: The complete updated history from database
        """

        if self.assets_history_df is None:
            # Initialize asset_history_handler with all symbols, to ensure that full
            # portfolio history can be derived + up-to-date
            asset_history_handler = AssetHistoryHandler()

            # Get asset history from DB into dataframe
            self.assets_history_df = asset_history_handler.history_df

        # Aggregate over dates to get total portfolio value for each day
        daily_portfolio_value_df = self.assets_history_df.groupby('Date')['Value'].sum()

        # Convert from Series to DataFrame
        daily_portfolio_value_df = daily_portfolio_value_df.reset_index()

        # Set date column as index
        daily_portfolio_value_df['Date'] = pd.to_datetime(daily_portfolio_value_df['Date'])
        # daily_portfolio_value_df = daily_portfolio_value_df.set_index('Date')

        # Filter to just start_date to today
        if start_date is not None:
            daily_portfolio_value_df = \
                daily_portfolio_value_df[daily_portfolio_value_df['Date'] >= start_date]

        column_conversion_map = {
            'date': 'Date',
            'value': 'Value',
        }

        # OPTIMIZATION: Batch insert using executemany() instead of individual INSERTs
        with MysqlDB(dbcfg) as db:
            if overwrite:
                sql = """REPLACE INTO portfolio_history (date, value)
                         VALUES (%s, %s)"""
            else:
                sql = """INSERT IGNORE INTO portfolio_history (date, value)
                         VALUES (%s, %s)"""

            # Prepare values as list of tuples
            values = [
                (row['Date'].date(), float(row['Value']))
                for _, row in daily_portfolio_value_df.iterrows()
            ]

            if values:
                db.cursor.executemany(sql, values)
                print(f"✓ Batch inserted {len(values)} portfolio history rows")

        # OPTIMIZATION: Return the full history instead of requiring a re-read
        return self.get_history()

    def get_history(self) -> pd.DataFrame:
        """
        Get portfolio history from DB and place into dataframe
        
        Returns:
            history_df (pd.DataFrame): 
                Date, Value
        """
        history_df = mysql_to_df(read_portfolio_history_query, 
                                 read_portfolio_history_columns, dbcfg, cached=True)
        
        return history_df
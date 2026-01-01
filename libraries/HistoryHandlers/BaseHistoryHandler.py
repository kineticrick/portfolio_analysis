#!/usr/bin/env python
import datetime
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

import pandas as pd
from pandas.tseries.offsets import Day, BDay
from libraries.db import dbcfg, MysqlDB
from libraries.db.mysql_helpers import mysql_cache_evict
from libraries.globals import MYSQL_CACHE_HISTORY_TAG

class BaseHistoryHandler:
    # Placeholder for SQL to create history table in DB
    create_history_table_sql = None
    
    def __init__(self) -> None:
        """ 
        Initialize handler with updated history from DB, for either assets or total portfolio
        """
        # Initialize {asset,portfolio,asset_hypothetical}_history table in DB, if not already present
        self.gen_table()
        
        # Retrieve history from DB
        self.history_df = self.get_history()
        
        # OPTIMIZATION: Remove double-read by having set_history() return updated data
        if not self.history_df.empty:

            # Get latest date from dataframe
            latest_history_date = self.history_df['Date'].max()

            today = datetime.datetime.today()
            previous_business_date = today  - BDay(1)
            previous_business_date = previous_business_date.date()

            # If latest history date in DB is behind most recent trading day,
            # update history from day after latest date to today

            # OR if yesterday was a weekend day and latest
            # history date is behind that, then also update history
            # to fill in weekend gaps

            yesterday = today - Day(1)
            yesterday = yesterday.date()
            yesterday_weekend = yesterday.weekday() >= 5

            if latest_history_date < previous_business_date or \
                (yesterday_weekend and latest_history_date < yesterday):
                    # set_history() now returns the updated data, no need to re-read!
                    updated_df = self.set_history(start_date=latest_history_date + Day(1))
                    # Clear cache to ensure updated history is retrieved if needed later
                    mysql_cache_evict(MYSQL_CACHE_HISTORY_TAG)
                    if updated_df is not None and not updated_df.empty:
                        # Merge new data with existing
                        self.history_df = updated_df

        # If dataframe is empty, update history from start of time to today
        else:
            # set_history() returns the full history, no need to re-read!
            self.history_df = self.set_history()
            # Clear cache to ensure updated history is retrieved if needed later
            mysql_cache_evict(MYSQL_CACHE_HISTORY_TAG)
            
        self.latest_history_date = self.get_latest_date()
    
    def gen_table(self) -> None:
        """
        Generate asset_history table in DB, if not already present
        """
        with MysqlDB(dbcfg) as db:
            db.execute(self.create_history_table_sql)

        # TODO: Figure out better way to instantiate table if not present 
        
    def get_history(self) -> pd.DataFrame:
        """Retrieve history from database. Implemented by subclasses."""
        pass

    def set_history(self, start_date=None) -> pd.DataFrame:
        """
        Update history in database and return the full updated dataframe.
        This avoids the need to re-read from DB after writing.

        Returns:
            pd.DataFrame: The complete history including newly added data
        """
        pass
    
    def get_latest_date(self) -> str:
        """
        Get date of most recent entry available in DB
        
        Returns:
            latest_date (str): Latest date in DB
        """
        return self.history_df['Date'].max()
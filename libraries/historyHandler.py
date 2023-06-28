#!/usr/bin/env python 
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import datetime
import pandas as pd
from pandas.tseries.offsets import BDay

from libraries.mysqldb import MysqlDB
from libraries.dbcfg import *
from libraries.sql import (create_assets_history_table_sql, insert_update_assets_history_sql, 
                           insert_ignore_assets_history_sql, read_assets_history_query, 
                           read_assets_history_columns)
from libraries.pandas_helpers import print_full, mysql_to_df
from libraries.helpers import gen_assets_historical_value

class HistoryHandler:
    def __init__() -> None:
        pass
    
    def get_history() -> None:
        pass
    
    def set_history() -> None:
        pass
    
    def get_latest_date() -> None:
        pass
    
    
class AssetHistoryHandler(HistoryHandler):
    def __init__(self, symbols: list=[]) -> None: 
        """ 
        For all symbols in symbols, initialize object with updated 
        asset histories from DB. (Date, symbol, quantity, price, value)
        
        If 'symbols' is empty, initialize object with all asset histories from DB.
        """
        assert(isinstance(symbols, list))
        self.gen_table()
        self.symbols = symbols
        
        # Retrieve history from DB
        history_df = self.get_history()
        if not history_df.empty: 
            # Get latest date from dataframe
            latest_history_date = history_df['Date'].max()
            print(latest_history_date)
            
            # If latest date is behind most previous trading day, 
            # update history from day after latest date to today
            today = datetime.datetime.today()
            previous_business_date = today  - BDay(1)
            previous_business_date = previous_business_date.date()
            
            if latest_history_date < previous_business_date:
                self.set_history(start_date=latest_history_date + BDay(1))

        # If dataframe is empty, update history from start of time to today
        else:
            self.set_history()
            
        self.history_df = self.get_history()
        self.latest_history_date = self.get_latest_date()
            
    def gen_table(self) -> None:
        """
        Generate asset_history table in DB, if not already present
        """
        with MysqlDB(dbcfg) as db:
            db.execute(create_assets_history_table_sql)
            
        # TODO: Figure out better way to instantiate table if not present 
        
    def set_history(self, start_date: str=None, overwrite: bool=False) -> None:
        """
        For all symbols in self.symbols, update DB with asset history info 
        from start_date to today
        
        If overwrite is True, overwrite all existing history in DB with new derived history
        Else, only add new history to DB (append-only)
        
        Args:
            start_date (str): Date to start history from (inclusive)
        """
        # Retrieve daily quantity + value data for all symbols in self.symbols
        print(start_date.date())
        
        assets_historical_data_df = \
            gen_assets_historical_value(self.symbols, cadence='daily', 
                                        start_date=start_date)
        print_full(assets_historical_data_df)
        
        column_conversion_map = {
            'date': 'Date',
            'symbol': 'Symbol',
            'quantity': 'Quantity',
            'closing_price': 'Close', 
            'value': 'Value'
        }
        
        # Generate Insert/Update SQL for each row in assets_historical_data_df
        with MysqlDB(dbcfg) as db:
            for _, history_data in assets_historical_data_df.iterrows():
                insertion_dict = {}
                for k, v in column_conversion_map.items():
                    insertion_dict[k] = history_data[v]
                    
                if overwrite:
                    insertion_sql = \
                        insert_update_assets_history_sql.format(**insertion_dict)
                else: 
                    insertion_sql = \
                        insert_ignore_assets_history_sql.format(**insertion_dict)
                        
                db.execute(insertion_sql)
            
               
    def get_history(self) -> pd.DataFrame:
        """
        For all symbols in self.symbols, get asset history from DB into dataframe
        
        
        Returns:
            history_df (pd.DataFrame): 
                Date, Symbol, Quantity, Price (Closing), Value 
        """
        symbols_clause = \
            "(" + ", ".join([f"'{symbol}'" for symbol in self.symbols]) + ")"
        symbols_str = " WHERE symbol IN " + symbols_clause if len(self.symbols) > 0 else ""
        
        query = read_assets_history_query + symbols_str
        history_df = mysql_to_df(query, read_assets_history_columns, dbcfg)
        
        return history_df
    
    def get_latest_date(self) -> str:
        """
        For all symbols in self.symbols, get latest date from DB
        
        Returns:
            latest_date (str): Latest date from DB
        """
        return self.history_df['Date'].max()

    
    # def validate_history(self) -> None:
        """ 
        Ensure that all expected dates are present and accounted for 
        (ie there are no unexpected gaps in business/trading days for assets indicated)
        """
        

# asset_history_handler = AssetHistoryHandler()
# print_full(asset_history_handler.history_df)
# print(asset_history_handler.latest_history_date)
# asset_history_handler.set_history()
# history_df = asset_history_handler.get_history()
# print_full(history_df)
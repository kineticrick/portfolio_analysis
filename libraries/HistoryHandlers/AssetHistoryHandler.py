import os
import sys
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from libraries.db import dbcfg, MysqlDB
from libraries.db.sql import (create_assets_history_table_sql, insert_update_assets_history_sql, 
                           insert_ignore_assets_history_sql, read_assets_history_query, 
                           read_assets_history_columns)
from libraries.HistoryHandlers import BaseHistoryHandler
from libraries.pandas_helpers import print_full, mysql_to_df
from libraries.helpers import gen_assets_historical_value

class AssetHistoryHandler(BaseHistoryHandler):
    create_history_table_sql = create_assets_history_table_sql
    
    def __init__(self, symbols: list=[]) -> None: 
        """ 
        For all symbols in symbols, initialize object with updated 
        asset histories from DB. (Date, symbol, quantity, price, value)
        
        If 'symbols' is empty, initialize object with all asset histories from DB.
        """
        assert(isinstance(symbols, list))
        self.symbols = symbols   

        super().__init__()

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
        assets_historical_data_df = \
            gen_assets_historical_value(self.symbols, cadence='daily', 
                                        start_date=start_date, 
                                        include_exit_date=False)
        column_conversion_map = {
            'date': 'Date',
            'symbol': 'Symbol',
            'quantity': 'Quantity',
            'cost_basis': 'CostBasis',
            'closing_price': 'ClosingPrice', 
            'value': 'Value',
            'percent_return': 'PercentReturn',
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
                Date, Symbol, Quantity, ClosingPrice, Value, CostBasis  
        """
        symbols_clause = \
            "(" + ", ".join([f"'{symbol}'" for symbol in self.symbols]) + ")"
        symbols_str = " WHERE symbol IN " + symbols_clause if len(self.symbols) > 0 else ""
        
        query = read_assets_history_query + symbols_str
        history_df = mysql_to_df(query, read_assets_history_columns, dbcfg, cached=True)
        return history_df
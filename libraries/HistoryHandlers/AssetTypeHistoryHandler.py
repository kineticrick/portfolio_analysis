import os
import sys
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from libraries.db import dbcfg, MysqlDB
from libraries.db.sql import (create_asset_types_history_table_sql, 
                              insert_update_asset_types_history_sql,
                              insert_ignore_asset_types_history_sql,
                              read_asset_types_history_query,
                              read_asset_types_history_columns)
from libraries.HistoryHandlers import BaseHistoryHandler
from libraries.pandas_helpers import print_full, mysql_to_df
from libraries.helpers import gen_aggregated_historical_value

class AssetTypeHistoryHandler(BaseHistoryHandler):
    create_history_table_sql = create_asset_types_history_table_sql
    
    def __init__(self) -> None: 
        """ 
        Initialize object with updated asset_type histories from DB. 
        (Date, asset_type, value)
        """
        super().__init__()

    def set_history(self, start_date: str=None, overwrite: bool=False) -> None:
        """
        Update DB with asset_type history info from start_date to today
        
        If overwrite is True, overwrite all existing history in DB with new derived history
        Else, only add new history to DB (append-only)
        
        Args:
            start_date (str): Date to start history from (inclusive)
        """
        # Retrieve daily value data for all asset_types
        asset_types_historical_data_df = \
            gen_aggregated_historical_value(dimension='AssetType',
                                            start_date=start_date)
            
        column_conversion_map = {
            'date': 'Date',
            'asset_type': 'AssetType',
            'avg_percent_return': 'AvgPercentReturn',
        }
        
        # Generate Insert/Update SQL for each row in asset_types_historical_data_df
        with MysqlDB(dbcfg) as db:
            for _, history_data in asset_types_historical_data_df.iterrows():
                insertion_dict = {}
                for k, v in column_conversion_map.items():
                    insertion_dict[k] = history_data[v]
                    
                if overwrite:
                    insertion_sql = \
                        insert_update_asset_types_history_sql.format(**insertion_dict)
                else: 
                    insertion_sql = \
                        insert_ignore_asset_types_history_sql.format(**insertion_dict)
                db.execute(insertion_sql)
            
    def get_history(self) -> pd.DataFrame:
        """
        Get asset_type history from DB into dataframe
        
        
        Returns:
            history_df (pd.DataFrame): 
                Date, AssetType, AvgPercentReturn
        """
        history_df = mysql_to_df(read_asset_types_history_query, 
                                 read_asset_types_history_columns, dbcfg, cached=True)
        return history_df
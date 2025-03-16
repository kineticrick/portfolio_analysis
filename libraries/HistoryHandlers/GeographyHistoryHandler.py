import os
import sys
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from libraries.db import dbcfg, MysqlDB
from libraries.db.sql import (create_geography_history_table_sql, 
                              insert_update_geography_history_sql,
                              insert_ignore_geography_history_sql,
                              read_geography_history_query,
                              read_geography_history_columns)
from libraries.HistoryHandlers import BaseHistoryHandler
from libraries.pandas_helpers import print_full, mysql_to_df
from libraries.helpers import gen_aggregated_historical_value

class GeographyHistoryHandler(BaseHistoryHandler):
    create_history_table_sql = create_geography_history_table_sql
    
    def __init__(self) -> None: 
        """ 
        Initialize object with updated geography histories from DB. 
        (Date, geography, value)
        """
        super().__init__()

    def set_history(self, start_date: str=None, overwrite: bool=False) -> None:
        """
        Update DB with geography history info from start_date to today
        
        If overwrite is True, overwrite all existing history in DB with new derived history
        Else, only add new history to DB (append-only)
        
        Args:
            start_date (str): Date to start history from (inclusive)
        """
        # Retrieve daily value data for all geography
        geography_historical_data_df = \
            gen_aggregated_historical_value(dimension='Geography',
                                            start_date=start_date)

        column_conversion_map = {
            'date': 'Date',
            'geography': 'Geography',
            'avg_percent_return': 'AvgPercentReturn',
        }
        
        # Generate Insert/Update SQL for each row in geography_historical_data_df
        with MysqlDB(dbcfg) as db:
            for _, history_data in geography_historical_data_df.iterrows():
                insertion_dict = {}
                for k, v in column_conversion_map.items():
                    insertion_dict[k] = history_data[v]
                    
                if overwrite:
                    insertion_sql = \
                        insert_update_geography_history_sql.format(**insertion_dict)
                else: 
                    insertion_sql = \
                        insert_ignore_geography_history_sql.format(**insertion_dict)
                db.execute(insertion_sql)
            
    def get_history(self) -> pd.DataFrame:
        """
        Get geography history from DB into dataframe
        
        
        Returns:
            history_df (pd.DataFrame): 
                Date, Geography, AvgPercentReturn
        """
        history_df = mysql_to_df(read_geography_history_query, 
                                 read_geography_history_columns, dbcfg, cached=True)
        return history_df
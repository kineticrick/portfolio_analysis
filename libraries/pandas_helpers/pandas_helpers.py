import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

import pandas as pd
from libraries.globals import MYSQL_CACHE_ENABLED
from libraries.db import mysql_query

def print_full(df):
    """
    Prints the entirety of a PD dataframe, not just the shortened version
    """
    if isinstance(df, pd.DataFrame):
        num_columns = len(df.columns.values)
    elif isinstance(df, pd.Series):
        num_columns = 1
    pd.set_option('display.max_rows', len(df))
    pd.set_option('display.max_columns', num_columns + 1)
    pd.set_option('display.width', None)
    print(df)
    pd.reset_option('display.max_rows')
    pd.reset_option('display.max_columns')
    pd.reset_option('display.width')

def mysql_to_df(query, columns, dbcfg, cached=False, verbose=False): 
    """
    Convert results of mysql query to a pandas dataframe
    """
    if verbose:
        print(f"Columns: {', '.join(columns)}")

    if MYSQL_CACHE_ENABLED and cached:
        mysql_func = mysql_query
    else: 
        # print("NOTE: Not using cache: " + query)
        mysql_func = mysql_query.__wrapped__

    mysql_res = mysql_func(query, dbcfg, verbose)    
    df_data = [list(tup) for tup in mysql_res]
    df = pd.DataFrame(df_data, columns=columns)
    
    # Cast all numerical columns to float
    df = df.apply(pd.to_numeric, errors='ignore')
    
    return df
    
    
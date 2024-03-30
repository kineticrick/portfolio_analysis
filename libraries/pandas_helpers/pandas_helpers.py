import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

import pandas as pd
from libraries.db import MysqlDB
from libraries.globals import MYSQL_CACHE_ENABLED, MYSQL_CACHE_TTL
from diskcache import Cache

cache = Cache("cache")

TDAMERITRADE_CSV_TO_DB_COL_NAMES = {
    "Qty": "Quantity",
    "Mkt value": "MarketValue",
    "Cost": "CostBasis",
    "Div yield": "DividendYield",
}

SCHWAB_CSV_VALID_COLUMNS = [
    'Symbol',
    'Quantity',
    'Cost Basis',
    'Dividend Yield',
] 

def get_brokerage_data_from_csv(csv_path: str) -> pd.DataFrame:
    """
    Converts the CSV file at the given path to a pandas dataframe 
    """
    df = pd.read_csv(csv_path)
    
    # Filter only columns that we need 
    df = df[SCHWAB_CSV_VALID_COLUMNS]
    
    # Clean up data - remove % from dividend yield, $ from cost basis
    df['Dividend Yield'] = df['Dividend Yield'].fillna('0')
    df['Dividend Yield'] = df['Dividend Yield'].str.rstrip('%')
    df['Cost Basis'] = df['Cost Basis'].str.lstrip('$')
    df['Cost Basis'] = df['Cost Basis'].str.replace(',', '')

    return df

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

@cache.memoize(expire=MYSQL_CACHE_TTL)
def mysql_query(query, dbcfg):
    with MysqlDB(dbcfg) as db:
        return db.query(query)

def mysql_to_df(query, columns, dbcfg, cached=False, verbose=False): 
    """
    Convert results of mysql query to a pandas dataframe
    """
    if verbose:
        print(f"Query: {query}")
        print(f"Columns: {', '.join(columns)}")

    if MYSQL_CACHE_ENABLED and cached:
        mysql_func = mysql_query
    else: 
        print("NOTE: Not using cache: " + query)
        mysql_func = mysql_query.__wrapped__

    mysql_res = mysql_func(query, dbcfg)    
    df_data = [list(tup) for tup in mysql_res]
    df = pd.DataFrame(df_data, columns=columns)
    
    # Cast all numerical columns to float
    df = df.apply(pd.to_numeric, errors='ignore')
    
    return df

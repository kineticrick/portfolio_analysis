import pandas as pd

from mysqldb import MysqlDB

TDAMERITRADE_CSV_TO_DB_COL_NAMES = {
    "Qty": "Quantity",
    "Mkt value": "MarketValue",
    "Cost": "CostBasis",
    "Div yield": "DividendYield",
}

def get_brokerage_data_from_csv(csv_path: str) -> pd.DataFrame:
    """
    Converts the CSV file at the given path to a pandas dataframe 
    """
    df = pd.read_csv(csv_path)
    
    # Convert dataframe column names based on dictionary
    df = df.rename(columns=TDAMERITRADE_CSV_TO_DB_COL_NAMES)

    return df

def print_full(df):
    """
    Prints the entirety of a PD dataframe, not just the shortened version
    """
    pd.set_option('display.max_rows', len(df))
    pd.set_option('display.max_columns', len(df.columns.values))
    # pd.set_option('display.max_columns', 1000)
    pd.set_option('display.width', None)
    print(df)
    pd.reset_option('display.max_rows')
    pd.reset_option('display.max_columns')
    pd.reset_option('display.width')

def mysql_to_df(query, columns, dbcfg, verbose=False): 
    """
    Convert results of mysql query to a pandas dataframe
    """
    if verbose:
        print(f"Query: {query}")
        print(f"Columns: {', '.join(columns)}")
    
    with MysqlDB(dbcfg) as db:
        mysql_res = db.query(query)

    df_data = [list(tup) for tup in mysql_res]
    df = pd.DataFrame(df_data, columns=columns)
    
    return df
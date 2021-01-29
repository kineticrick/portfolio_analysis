import pandas as pd

from mysqldb import MysqlDB

def print_full(df):
    """
    Prints the entirety of a PD dataframe, not just the shortened version
    """
    pd.set_option('display.max_rows', len(df))
    pd.set_option('display.max_columns', len(df.columns.values))
    print(df)
    pd.reset_option('display.max_rows')
    pd.reset_option('display.max_columns')

def mysql_to_df(query, columns, dbcfg): 
    with MysqlDB(dbcfg) as db:
        mysql_res = db.query(query)

    df_data = [list(tup) for tup in mysql_res]
    df = pd.DataFrame(df_data, columns=columns)
    
    return df
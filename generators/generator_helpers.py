import csv
import os
import numpy as np
import pandas as pd

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from libraries.db import MysqlDB, dbcfg
from libraries.db.sql import (drop_summary_table_sql, create_summary_table_sql,
                              insert_summary_sql, asset_name_query, 
                              asset_name_columns)
from libraries.globals import (TRADES_DICT_KEYS, DIVIDENDS_DICT_KEYS, 
                               SCHWAB_CSV_VALID_COLUMNS)
from libraries.pandas_helpers import mysql_to_df


### importer.py Helpers ###

def build_file_lists(file_dirs: dict) -> dict:
    """
    Given a dictionary of {object_type:directory}, where directory holds files 
    of object_type CSV's, return a dictionary of lists of files in each directory
    """
    file_lists = {}
    for object_type, dir in file_dirs.items():
        file_lists[object_type] = \
            [os.path.join(dir,f) for f in os.listdir(dir) 
             if os.path.isfile(os.path.join(dir, f)) and f.endswith('csv')]

    return file_lists

def process_csvs(object_type: str, csv_files: str, brokerage_name: str="") -> list[dict]:
    """
    For any object_type contained in multiple csv_files - 
    transactions, entities, splits, acquisitions - 
    extract the data and return a list of dictionaries. For transactions, also add the
    brokerage name.
    """
    
    assert object_type in ['transactions', 'entities', 'splits', 'acquisitions']
    if object_type == 'transactions':
        assert brokerage_name != ""
    
    all_objects = []
    
    for csv_file in csv_files:
        with open(csv_file) as file: 
            reader = csv.DictReader(file)
            for row in reader: 
                object_dict = {}
                row = {k.lower(): v for k, v in row.items()}
                object_dict['symbol'] = row['symbol']
                
                match object_type:
                    case 'entities':
                        object_dict['name'] = row['name']
                        object_dict['asset_type'] = row['asset_type']
                        object_dict['sector'] = row['sector']
                    case 'splits':
                        object_dict['record_date'] = datetime.strptime(row.get('record_date'), "%m/%d/%Y").strftime("%Y-%m-%d")
                        object_dict['distribution_date'] = datetime.strptime(row.get('distribution_date'), "%m/%d/%Y").strftime("%Y-%m-%d")
                        object_dict['multiplier'] = row['multiplier']
                    case 'acquisitions':
                        object_dict['date'] = datetime.strptime(row.get('date'), "%m/%d/%Y").strftime("%Y-%m-%d")
                        object_dict['acquirer'] = row['acquirer']
                        object_dict['conversion_ratio'] = row['conversion_ratio']
                    case 'transactions':
                        match brokerage_name:
                            case 'schwab':
                                try:
                                    object_dict['date'] = datetime.strptime(row.get('date'), "%m/%d/%Y").strftime("%Y-%m-%d")
                                except:
                                    tmp_date = row.get('date').split(' ')[0]
                                    object_dict['date'] = datetime.strptime(tmp_date, "%m/%d/%Y").strftime("%Y-%m-%d")
                                if "reinvest" in row['action'].lower():
                                    continue
                                if "div" in row['action'].lower():
                                    object_dict['action'] = "dividend"
                                    object_dict['dividend'] = row['amount'].strip('$')
                                else:
                                    object_dict['action'] = row['action'].lower()
                                    object_dict['num_shares'] = row['quantity']
                                    object_dict['price_per_share'] = row['price'].strip('$')
                                    object_dict['total_price'] = row['amount'].strip('-').strip('$')
                            case 'tdameritrade':
                                object_dict['date'] = datetime.strptime(row.get('date'), "%m/%d/%Y").strftime("%Y-%m-%d")
                                description = row['description'].lower()
                                if "dividend" in description:
                                    object_dict['action'] = "dividend"
                                    if "~" in description:
                                        object_dict['symbol'] = description.split('~')[1]
                                    object_dict['dividend'] = row['amount']
                                else:
                                    if "bought" in description: 
                                        object_dict['action'] = "buy"
                                    elif "sold" in description:
                                        object_dict['action'] = "sell"
                                    object_dict['num_shares'] = row['quantity']
                                    object_dict['price_per_share'] = row['price'].strip('$')
                                    object_dict['total_price'] = row['amount'].strip('-').strip('$')
                            case 'wallmine':
                                object_dict['date'] = row['date']
                                object_dict['action'] = row['type']
                                if row['type'] == 'dividend': 
                                    object_dict['dividend'] = row['current_value'].strip('-')
                                else: 
                                    object_dict['num_shares'] = row['shares']
                                    object_dict['price_per_share'] = row['cost_per_share']
                                    object_dict['total_price'] = row['total_cost'].strip('-')
                        if object_dict.get('action') is None or \
                                object_dict['action'] not in ('buy', 'sell', 'dividend'): 
                            continue
                        object_dict['symbol'] = object_dict['symbol'].upper()
                all_objects.append(object_dict)
    return all_objects


def cleanup_transactions(transactions: list[dict]) -> list[dict]:
    """
    Perform one-off translations, fixes, etc, to normalize 
    specific pieces of data before its ingested
    """
    for tx in transactions:
        # TD Ameritrade prints Brown-Forman as "BF B" in their logs.
        # Throws things out of wack
        if tx['symbol'] == "BF B":
            tx['symbol'] = "BF.B"
            
    return transactions

def validate_transactions(transactions: list[dict], entities: list[dict]) -> list[dict]:
    """
    Perform various checks on the transactions to ensure validity
    """
    
    # Get list of all symbols from entities
    entity_symbols = [e['symbol'] for e in entities]
    missing_entities = []
    
    try: 
        for tx in transactions: 
            # Actions are one of 3 valid types
            assert tx['action'] in ['buy', 'sell', 'dividend']
            
            # All keys are present and only accepted keys are present
            if tx['action'] in ("buy", "sell"):
                assert sorted(tx.keys()) == sorted(TRADES_DICT_KEYS)
                assert float(tx['total_price']) 
            elif tx['action'] == 'dividend':
                assert sorted(tx.keys()) == sorted(DIVIDENDS_DICT_KEYS)
                assert float(tx['dividend'])
            
            # Symbols are valid length and type
            assert 1 <= len(tx['symbol']) <= 4
            assert datetime.strptime(tx['date'], "%Y-%m-%d")
            
            # Symbol is in list of entities
            if tx['symbol'] not in entity_symbols:
                missing_entities.append(tx['symbol'])
    except: 
        print("ERROR: Problem found with transaction:")
        print(tx)
        print()
        raise   

    if missing_entities:
        print("ERROR: The following symbols are missing from entities:")
        print(",".join(sorted(set(missing_entities))))
        print()
        raise ValueError("Missing entities found in transactions")
    
    return transactions

def mysql_execute(query, verbose=True):
    """
    Execute a MySQL query
    """
    if verbose: 
        print(f"Query: {query}")
    with MysqlDB(dbcfg) as db:
        return db.execute(query)       
    
    
### summary_table_generator.py Helpers ###

def process_master_log(master_log_df: pd.DataFrame) -> pd.DataFrame:
    """
    Process the master log of all actions, and return a summary table of 
    positions

    Args:
        master_log_df (pd.DataFrame): Master log of all actions, across all 
        assets

    Returns:
        pd.DataFrame: Summary table of positions
    """
    # Setup temporary dicts to hold running counts and states of each asset
    share_count = defaultdict(int)
    total_dividend = defaultdict(Decimal)
    first_date = defaultdict(str)
    last_date = defaultdict(str)
    
    for _, event in master_log_df.iterrows():
        date = event['Date']
        symbol = event['Symbol']
        action = event['Action']
        quantity = event['Quantity']
        dividend = event['Dividend']
        multiplier = event['Multiplier']
        acquirer = event['Acquirer']
        target = event['Target']
        
        match action:
            case 'buy': 
                # If first buy, set first date to date of buy
                if share_count[symbol] == 0:
                    first_date[symbol] = date
                
                # Increase quantity by # of shares bought and 
                # set last date to date of buy
                share_count[symbol] += quantity
                last_date[symbol] = date

            case 'sell':
                # Reduce quantity by # of shares sold
                share_count[symbol] -= quantity
            
            case 'dividend':
                # Increase dividend total for asset
                total_dividend[symbol] += Decimal(dividend)
                
            case 'split':
                # Multiply share count by split multiplier
                share_count[symbol] *= multiplier

            case 'acquisition-target':
                # Determine converted amount of shares for target, add to acquirer's amount
                multiplied_shares = int(share_count[symbol] * multiplier)
                share_count[acquirer] += multiplied_shares
                
                # Remove shares from target company 
                share_count[symbol] = 0   
    
    # Convert dicts to list of dicts for dataframe        
    summary_list = []
    for symbol, quantity in share_count.items():
        if quantity == 0: 
            continue
        asset_summary = {
            'Symbol': symbol,
            'Quantity': quantity,
            'Total Dividend': total_dividend[symbol],
            'First Date Purchased': first_date[symbol],
            'Last Date Purchased': last_date[symbol],
        }
        summary_list.append(asset_summary)
        
    return pd.DataFrame(summary_list)

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
    
    # Before summing up quantities, convert to numerical types
    df['Quantity'] = df['Quantity'].astype(int)
    df['Cost Basis'] = df['Cost Basis'].astype(float)
    
    # Because we're pulling data from multiple brokerage accounts, and they can hold
    # the same asset, we need to group by symbol and sum up the quantities
    df = df.groupby('Symbol').agg({'Quantity': 'sum', 
                                   'Cost Basis': 'sum', 
                                   'Dividend Yield': 'first'}).reset_index()
    
    return df

def validate_summary_table(summary_df: pd.DataFrame, 
                           brokerage_df: pd.DataFrame) -> list:
    """
    Compare summary table to brokerage data to ensure 
    that summary table is accurate
    """
    errors = defaultdict(list)
    
    for _, brokerage_asset in brokerage_df.iterrows(): 
        # Make sure that brokerage symbol exists in summary data
        symbol = brokerage_asset['Symbol']
        summary_asset_info = summary_df.loc[summary_df['Symbol'] == symbol]
        
        if summary_asset_info.empty:
            error_msg = f"Brokerage asset {symbol} doesn't appear in summary data"
            errors['Missing Assets'].append(error_msg)
            continue
              
    
    for _, summary_asset in summary_df.iterrows():
        # Make sure that custom-derived symbol exists in brokerage data
        symbol = summary_asset['Symbol']
        brokerage_asset_info = brokerage_df.loc[brokerage_df['Symbol'] == symbol]
        
        if brokerage_asset_info.empty:
            error_msg = f"Summary asset {symbol} doesn't appear in brokerage data"
            errors['Missing Assets'].append(error_msg)
            continue
        
        # Make sure that summary number of shares matches brokerage data
        quantity = summary_asset['Quantity']
        brokerage_shares = brokerage_asset_info['Quantity'].values[0].round()
        
        if quantity != brokerage_shares:
            error_msg = f"Number of shares for {symbol} doesn't match" + \
                f"brokerage data. Summary:{quantity} != Brokerage:{brokerage_shares}."
            errors['Shares quantity mismatch'].append(error_msg)
    
    return errors

def integrate_brokerage_data(summary_df: pd.DataFrame, 
                             brokerage_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add cost basis, dividend yield from brokerage data to summary data
    """
    for _, summary_asset in summary_df.iterrows():
        symbol = summary_asset['Symbol']
        brokerage_asset_info = brokerage_df.loc[brokerage_df['Symbol'] == symbol]
        
        # Skip if brokerage data doesn't have info for symbol 
        # Already flagged in validate_summary_table
        if brokerage_asset_info.empty:
            continue
        
        # Merge brokerage Cost Basis into summary  
        cost_basis = brokerage_asset_info['Cost Basis'].values[0]
        summary_df.loc[summary_df['Symbol'] == symbol, 'Cost Basis'] = cost_basis

        # Merge brokerage dividend yield into summary  
        dividend_yield = brokerage_asset_info['Dividend Yield'].values[0].rstrip('%')
        summary_df.loc[summary_df['Symbol'] == symbol, 'Dividend Yield'] = \
            dividend_yield
            
    return summary_df

def write_db(summary_df: pd.DataFrame, verbose: bool) -> None:
    """
    Write summary data to database
    """
    # Get asset full names from db and add to summary data
    asset_name_df = mysql_to_df(asset_name_query, asset_name_columns, dbcfg)
    summary_df = summary_df.merge(asset_name_df, on='Symbol', how='left')
    summary_df = summary_df.replace({np.nan: 0.00, '--': 0.00})

    with MysqlDB(dbcfg) as db:
        if verbose:
            print(drop_summary_table_sql)
        db.execute(drop_summary_table_sql)
        
        if verbose:
            print(create_summary_table_sql)
        db.execute(create_summary_table_sql)
        
        for _, asset in summary_df.iterrows(): 
            insertion_dict = {}
            insertion_dict['symbol'] = asset['Symbol']
            insertion_dict['name'] = asset['Name']
            insertion_dict['current_shares'] = asset['Quantity']
            insertion_dict['cost_basis'] = asset['Cost Basis']
            insertion_dict['first_purchase_date'] = asset['First Date Purchased']
            insertion_dict['last_purchase_date'] = asset['Last Date Purchased']
            insertion_dict['total_dividend'] = asset['Total Dividend']
            insertion_dict['dividend_yield'] = asset['Dividend Yield']
            
            sql = insert_summary_sql.format(**insertion_dict)
            if verbose: 
                print(sql)
            db.execute(sql)
        
    print()
    print("Summary table written to database")
    print()
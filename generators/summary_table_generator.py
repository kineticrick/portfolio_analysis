#!/usr/bin/env python
import argparse
import numpy as np
import os
import pandas as pd
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from collections import defaultdict
from decimal import Decimal
from libraries.dbcfg import *
from libraries.pandas_helpers import * 
from libraries.sql import *
from libraries.helpers import build_master_log



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
                total_dividend[symbol] += dividend
                
            case 'split':
                # Multiply share count by split multiplier
                share_count[symbol] *= multiplier

            case 'acquisition':
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
        cost_basis = brokerage_asset_info['CostBasis'].values[0]
        summary_df.loc[summary_df['Symbol'] == symbol, 'CostBasis'] = cost_basis

        # Merge brokerage dividend yield into summary  
        dividend_yield= brokerage_asset_info['DividendYield'].values[0].rstrip('%')
        summary_df.loc[summary_df['Symbol'] == symbol, 'DividendYield'] = \
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
            insertion_dict['cost_basis'] = asset['CostBasis']
            insertion_dict['first_purchase_date'] = asset['First Date Purchased']
            insertion_dict['last_purchase_date'] = asset['Last Date Purchased']
            insertion_dict['total_dividend'] = asset['Total Dividend']
            insertion_dict['dividend_yield'] = asset['DividendYield']
            
            sql = insert_summary_sql.format(**insertion_dict)
            if verbose: 
                print(sql)
            db.execute(sql)
        
    print()
    print("Summary table written to database")
    print()
            
            
def process_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Generate and validate summary table')
    parser.add_argument('brokerage_data_file', type=str, 
                        help='Brokerage data file to process (csv)')
    
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--validate-only', action='store_true',
                              help="Only validate summary table and exit")
    action_group.add_argument('--write-db', action='store_true', default=False, 
                              help="Write summary table to database")

    parser.add_argument('--silent', action='store_true', default=False,
                        help="Do not print sql statements")
    return parser.parse_args()
  
def main():
    # #TODO: Make this a command line argument
    # DIR = "/home/kineticrick/code/python/portfolio_analysis/files/position_summaries/"
    # # PATH = DIR + "tdameritrade_positions_05292023.csv"  
    
    args = process_args()
    
    master_log_df = build_master_log()
    summary_df = process_master_log(master_log_df)

    brokerage_df = get_brokerage_data_from_csv(args.brokerage_data_file)
    
    errors = validate_summary_table(summary_df, brokerage_df)
    
    summary_df = integrate_brokerage_data(summary_df, brokerage_df)
    
    # Sort summary_df by symbol
    summary_df = summary_df.sort_values(by=['Symbol'], ignore_index=True)
    
    print_full(summary_df) 
    print()
    print()
    
    if len(errors) > 0:
        print()
        print("Errors found:")
        print()
        for error_type, error_list in errors.items():
            print("{}".format(error_type.upper()))
            for count, error in enumerate(error_list):
                print("\t{}. {}".format(count+1, error))
            print()
    else:
        print()
        print("No Errors Found!")
        print()
    
    if args.write_db:
        print("\tProposed summary table and any potential errors are shown above. "
              "Would you like to write this to the database?")
        resp = \
            input("\tEnter 'y' to write to database, anything else to exit: ")
        
        print()
        if resp.lower() == 'y':
            write_db(summary_df, not args.silent)
        else: 
            exit(0)
    
if __name__ == "__main__":
    main()
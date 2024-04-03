#!/usr/bin/env python3

import csv
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from libraries.db.sql import *
from libraries.globals import FILEDIRS
from generators.generator_helpers import (build_file_lists, 
                                          process_csvs, 
                                          cleanup_transactions,
                                          validate_transactions,
                                          mysql_execute)

def main(): 
    # Build dictionary of file lists
    csv_files = build_file_lists(FILEDIRS)
    
    # Generate lists of dictionaries from CSVs
    acquisitions = process_csvs('acquisitions', csv_files['acquisitions'])
    entities = process_csvs('entities', csv_files['entities'])
    splits = process_csvs('splits', csv_files['splits'])
    wallmine_transactions = process_csvs('transactions',
                                         csv_files['wallmine_transactions'],
                                         brokerage_name='wallmine') 
    tdameritrade_transactions = process_csvs('transactions', 
                                             csv_files['tdameritrade_transactions'],
                                             brokerage_name='tdameritrade')
    schwab_transactions = process_csvs('transactions', 
                                       csv_files['schwab_transactions'],
                                       brokerage_name='schwab')
    
    # Aggregate, validate, and clean up transactions
    all_transactions = (wallmine_transactions + 
                        tdameritrade_transactions + 
                        schwab_transactions)
    all_transactions = validate_transactions(all_transactions)
    all_transactions = cleanup_transactions(all_transactions)
    
    # Create tables
    mysql_execute(create_acquisitions_table_sql)
    mysql_execute(create_entities_table_sql)
    mysql_execute(create_splits_table_sql)
    mysql_execute(create_trades_table_sql)
    mysql_execute(create_dividends_table_sql)
    
    # Insert data into tables
    for acquisition in acquisitions: 
        acquisition_sql = insert_acquisitions_sql.format(**acquisition)
        # print(acquisition_sql)
        mysql_execute(acquisition_sql)
        
    for entity in entities:
        entity_sql = insert_entities_sql.format(**entity)
        # print(entity_sql)
        mysql_execute(entity_sql)
        
    for split in splits:
        splits_sql = insert_splits_sql.format(**split)
        # print(splits_sql)
        mysql_execute(splits_sql)
        
    for transaction in all_transactions:
        if transaction['action'] in ('buy', 'sell'):
            tx_sql = insert_buysell_tx_sql.format(**transaction)
        elif transaction['action'] == 'dividend':
            tx_sql = insert_dividend_tx_sql.format(**transaction)
        # print(tx_sql)
        mysql_execute(tx_sql)
    
if __name__ == "__main__": 
    main()
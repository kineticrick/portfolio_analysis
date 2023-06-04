#!/usr/bin/env python3

import csv
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from libraries.mysqldb import MysqlDB
from datetime import datetime

from libraries.dbcfg import *
from libraries.sql import *
from libraries.pandas_helpers import * 

dir_root = "/home/kineticrick/code/python/portfolio_analysis"

filedirs = {'entities': os.path.join(dir_root, 'files/entities'), 
            'splits': os.path.join(dir_root, 'files/splits'),
            'acquisitions': os.path.join(dir_root, 'files/acquisitions'),
            'schwab_transactions': os.path.join(dir_root, 'files/transactions/schwab'),
            'tdameritrade_transactions': os.path.join(dir_root, 'files/transactions/tdameritrade'),
            'wallmine_transactions': os.path.join(dir_root, 'files/transactions/wallmine')
            }

# Build dictionary of file lists
csv_files = {}
for _type, dir in filedirs.items():
    files = [os.path.join(dir,f) for f in os.listdir(dir) 
             if os.path.isfile(os.path.join(dir, f)) and f.endswith('csv')]
    
    csv_files[_type] = files
    
trades_dict_keys = ['symbol', 'date', 'action', 
                         'num_shares', 'price_per_share', 'total_price']

dividends_dict_keys = ['symbol', 'date', 'action', 'dividend']

def get_transactions_from_csv(csvfiles, brokerage): 
    # Master list of all transactions
    all_transactions = []
    
    # Process each csv
    for csvfile in csvfiles: 
        with open(csvfile) as file:
            reader = csv.DictReader(file)
            for row in reader: 
                transact_dict = {}
                row = {k.lower(): v for k, v in row.items()}
                transact_dict['symbol'] = row.get('symbol')
                if brokerage == 'td_ameritrade' or brokerage == 'schwab': 
                    transact_dict['date'] = datetime.strptime(row.get('date'), "%m/%d/%Y").strftime("%Y-%m-%d")
                    description = row['description'].lower()
                    if "dividend" in description:
                        transact_dict['action'] = "dividend"
                        if "~" in description:
                            transact_dict['symbol'] = description.split('~')[1]
                        transact_dict['dividend'] = row['amount']
                    else:
                        if "bought" in description: 
                            transact_dict['action'] = "buy"
                        elif "sold" in description:
                            transact_dict['action'] = "sell"
                        if brokerage == 'schwab':
                            transact_dict['action'] = row['action'].lower()
                        transact_dict['num_shares'] = row['quantity']
                        transact_dict['price_per_share'] = row['price'].strip('$')
                        transact_dict['total_price'] = row['amount'].strip('-').strip('$')
                elif brokerage == 'wallmine': 
                    transact_dict['date'] = row['date']
                    transact_dict['action'] = row['type']
                    if row['type'] == 'dividend': 
                        transact_dict['dividend'] = row['current_value'].strip('-')
                    else: 
                        transact_dict['num_shares'] = row['shares']
                        transact_dict['price_per_share'] = row['cost_per_share']
                        transact_dict['total_price'] = row['total_cost'].strip('-')                    
                if transact_dict.get('action') is None or \
                        transact_dict['action'] not in ('buy', 'sell', 'dividend'): 
                    continue
                transact_dict['symbol'] = transact_dict['symbol'].upper()
                all_transactions.append(transact_dict)                
    return all_transactions

def get_entities_from_csv(csvfiles): 
    all_entities = []
    
    for csvfile in csvfiles:
        with open(csvfile) as file: 
            reader = csv.DictReader(file)
            for row in reader: 
                entity_dict = {}
                row = {k.lower(): v for k, v in row.items()}
                entity_dict['name'] = row['name']
                entity_dict['asset_type'] = row['asset_type']
                entity_dict['symbol'] = row['symbol']
                entity_dict['sector'] = row['sector']
                
                all_entities.append(entity_dict)
    return all_entities
            
def get_splits_from_csv(csvfiles): 
    #TODO: generalize this for entities, splits, etc
    all_splits = []
    
    for csvfile in csvfiles:
        with open(csvfile) as file: 
            reader = csv.DictReader(file)
            for row in reader: 
                split_dict = {}
                row = {k.lower(): v for k, v in row.items()}
                split_dict['record_date'] = datetime.strptime(row.get('record_date'), "%m/%d/%Y").strftime("%Y-%m-%d")
                split_dict['distribution_date'] = datetime.strptime(row.get('distribution_date'), "%m/%d/%Y").strftime("%Y-%m-%d")
                split_dict['symbol'] = row['symbol']
                split_dict['multiplier'] = row['multiplier']
                
                all_splits.append(split_dict)
    return all_splits
                        
def get_acquisitions_from_csv(csvfiles):
    all_acquisitions = []
    
    for csvfile in csvfiles:
        with open(csvfile) as file: 
            reader = csv.DictReader(file)
            for row in reader: 
                acquisition_dict = {}
                row = {k.lower(): v for k, v in row.items()}
                acquisition_dict['date'] = datetime.strptime(row.get('date'), "%m/%d/%Y").strftime("%Y-%m-%d")
                acquisition_dict['symbol'] = row['symbol']
                acquisition_dict['acquirer'] = row['acquirer']
                acquisition_dict['conversion_ratio'] = row['conversion_ratio']
                
                all_acquisitions.append(acquisition_dict)
    return all_acquisitions

def validate_transactions(transactions):
    try: 
        for transaction_dict in transactions: 
            # Actions are one of 3 valid types
            assert transaction_dict['action'] in ['buy', 'sell', 'dividend']
            
            # All keys are present and only accepted keys are present
            if transaction_dict['action'] in ("buy", "sell"):
                assert sorted(transaction_dict.keys()) == sorted(trades_dict_keys)
                assert float(transaction_dict['total_price']) 
            elif transaction_dict['action'] == 'dividend':
                assert sorted(transaction_dict.keys()) == sorted(dividends_dict_keys)
                assert float(transaction_dict['dividend'])
            
            # Symbols are valid length and type
            assert 1 <= len(transaction_dict['symbol']) <= 4
            assert datetime.strptime(transaction_dict['date'], "%Y-%m-%d")
    except: 
        print("ERROR: Problem found with transaction:")
        print(transaction_dict)
        print()
        raise          

def nullify_empty_values(transactions): 
    for transaction in transactions: 
        for k,v in transaction.items(): 
            if isinstance(v, str) and len(v) == 0: 
                transaction[k] = None
    
    return transactions 

def cleanup_transactions(transactions):
    """
    Perform one-off translations, fixes, etc, to normalize 
    specific pieces of data before its ingested
    """
    for tx in transactions:
        # TD Ameritrade prints Brown-Forman as "BF B" in their logs.
        # Throws things out of wack
        if tx['symbol'] == "BF B":
            tx['symbol'] = "BF.B"
    
def process_transactions():
    all_transactions = get_transactions_from_csv(csv_files['wallmine_transactions'], 'wallmine') + \
            get_transactions_from_csv(csv_files['tdameritrade_transactions'], 'td_ameritrade') + \
            get_transactions_from_csv(csv_files['schwab_transactions'], 'schwab')
    validate_transactions(all_transactions)
    cleanup_transactions(all_transactions)

    return all_transactions

with MysqlDB(dbcfg) as db:
    print(create_trades_table_sql)
    db.execute(create_trades_table_sql)
    
    print(create_dividends_table_sql)
    db.execute(create_dividends_table_sql)
    
    for transaction_dict in process_transactions():
        if transaction_dict['action'] in ('buy', 'sell'): 
            sql = insert_buysell_tx_sql.format(**transaction_dict)
        elif transaction_dict['action'] == 'dividend':
            sql = insert_dividend_tx_sql.format(**transaction_dict)
        print(sql)
        db.execute(sql)

    split_dicts = get_splits_from_csv(csv_files['splits'])
    print(drop_splits_table_sql)
    db.execute(drop_splits_table_sql)   
    print(create_splits_table_sql)
    db.execute(create_splits_table_sql)
  
    for split_dict in split_dicts:
        sql = insert_splits_sql.format(**split_dict)
        print(sql)
        db.execute(sql)

    entity_dicts = get_entities_from_csv(csv_files['entities'])
    print(drop_entities_table_sql)
    db.execute(drop_entities_table_sql)   
    print(create_entities_table_sql)
    db.execute(create_entities_table_sql)
      
    for entity_dict in entity_dicts:
        sql = insert_entities_sql.format(**entity_dict)
        print(sql)
        db.execute(sql)
        
    acquisition_dicts = get_acquisitions_from_csv(csv_files['acquisitions'])
    print(create_acquisitions_table_sql)
    db.execute(create_acquisitions_table_sql)
  
    for acquisition_dict in acquisition_dicts:
        sql = insert_acquisitions_sql.format(**acquisition_dict)
        print(sql)
        db.execute(sql)
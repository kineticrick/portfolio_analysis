import csv
import os

from datetime import datetime
from libraries.db import MysqlDB, dbcfg
from libraries.globals import (TRADES_DICT_KEYS, DIVIDENDS_DICT_KEYS)

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
                                    pass
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

def validate_transactions(transactions: list[dict]) -> list[dict]:
    """
    Perform various checks on the transactions to ensure validity
    """
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
    except: 
        print("ERROR: Problem found with transaction:")
        print(tx)
        print()
        raise   
    
    return transactions

def mysql_execute(query, verbose=True):
    """
    Execute a MySQL query
    """
    if verbose: 
        print(f"Query: {query}")
    with MysqlDB(dbcfg) as db:
        return db.execute(query)       
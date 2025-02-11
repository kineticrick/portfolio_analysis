import os

QUANTITY_ASSET_EVENTS = ['buy', 'sell', 'split', 'acquisition']
NON_QUANTITY_ASSET_EVENTS = ['dividend']
ASSET_EVENTS = QUANTITY_ASSET_EVENTS + NON_QUANTITY_ASSET_EVENTS

MASTER_LOG_COLUMNS = ['Date', 'Symbol', 'Action', 'Quantity', 
                      'Dividend', 'Multiplier', 'Acquirer']

CADENCE_MAP = {
    'daily': '1D',
    'weekly': '1W',
    'monthly': '1M',
    'quarterly': '3M',
    'yearly': '1Y',
}

BUSINESS_CADENCE_MAP = {
    'daily': 'B',
    'weekly': 'W-FRI',
    'monthly': 'BM',
    'quarterly': 'BQ',
    'half-yearly': '2BQ',
    'yearly': 'BY',
}

# Symbols which are not currently listed
SYMBOL_BLACKLIST = [
    'MGP',
    'DRE',
    'STOR',
    'BF.B',
    'CONE',
    'DIDI',
    'QTS',
    'ATVI',
    'PEAK', # Changed to "DOC"
    'SPWR',
]

MYSQL_CACHE_ENABLED = False
MYSQL_CACHE_HISTORY_TAG = 'historycaches'
MYSQL_CACHE_TTL = 60*60*1

### Generators ###

ROOT_DIR = "/home/kineticrick/code/python/portfolio_analysis"

FILEDIRS = {'entities': os.path.join(ROOT_DIR, 'files/entities'), 
            'splits': os.path.join(ROOT_DIR, 'files/splits'),
            'acquisitions': os.path.join(ROOT_DIR, 'files/acquisitions'),
            'schwab_transactions': os.path.join(ROOT_DIR, 'files/transactions/schwab'),
            'tdameritrade_transactions': os.path.join(ROOT_DIR, 'files/transactions/tdameritrade'),
            'wallmine_transactions': os.path.join(ROOT_DIR, 'files/transactions/wallmine')
            }

TRADES_DICT_KEYS = ['symbol', 'date', 'action',
                    'num_shares', 'price_per_share', 
                    'total_price', 'account_type']

DIVIDENDS_DICT_KEYS = ['symbol', 'date', 'action', 'dividend', 'account_type']

IMPORTER_VERBOSE = True

SCHWAB_CSV_VALID_COLUMNS = [
    'Symbol',
    'Quantity',
    'Cost Basis',
    'Dividend Yield',
] 

ACCOUNT_TYPES = ['Discretionary', 'Retirement']

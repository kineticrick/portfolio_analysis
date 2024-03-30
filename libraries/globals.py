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
]

MYSQL_CACHE_ENABLED = True
MYSQL_CACHE_TTL = 60*60*1
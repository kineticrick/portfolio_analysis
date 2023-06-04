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
    'yearly': 'BY',
}
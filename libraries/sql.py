# importer
create_trades_table_sql = \
    ("CREATE TABLE IF NOT EXISTS trades ("
    "date DATE NOT NULL, "
    "symbol VARCHAR(4) NOT NULL, "
    "action VARCHAR(10) NOT NULL, "
    "num_shares INT, "
    "price_per_share DECIMAL(13, 2), "
    "total_price DECIMAL(13, 2) NOT NULL, "
    "PRIMARY KEY (date, symbol, action, total_price))")

create_dividends_table_sql = \
    ("CREATE TABLE IF NOT EXISTS dividends ("
    "date DATE NOT NULL, "
    "symbol VARCHAR(4) NOT NULL, "
    "dividend DECIMAL(13, 2) NOT NULL, "
    "PRIMARY KEY (date, symbol, dividend))")

create_splits_table_sql = \
    ("CREATE TABLE IF NOT EXISTS splits ("
    "record_date DATE NOT NULL, "
    "distribution_date DATE NOT NULL, "
    "symbol VARCHAR(4) NOT NULL, "
    "multiplier INT NOT NULL, "
    "PRIMARY KEY (record_date, distribution_date, symbol, multiplier))")

create_entities_table_sql = \
    ("CREATE TABLE IF NOT EXISTS entities ("
     "name VARCHAR(100) NOT NULL, "
     "symbol VARCHAR(4) NOT NULL, "
     "asset_type VARCHAR(100) NOT NULL, "
     "sector VARCHAR(100) NOT NULL, "
     "PRIMARY KEY (name, symbol, asset_type, sector))")
    
create_acquisitions_table_sql = \
    ("CREATE TABLE IF NOT EXISTS acquisitions ("
    "date DATE NOT NULL, "
    "symbol VARCHAR(4) NOT NULL, "
    "acquirer VARCHAR(4) NOT NULL, "
    "conversion_ratio DECIMAL(13,5) NOT NULL, "
    "PRIMARY KEY (date, symbol, acquirer, conversion_ratio))")
    
insert_buysell_tx_sql = \
    ("INSERT IGNORE INTO trades"
     "(date, symbol, action, num_shares, price_per_share, total_price) "
     "VALUES ('{date}','{symbol}','{action}',{num_shares},"
             "{price_per_share},{total_price})")
    
insert_dividend_tx_sql = \
    ("INSERT IGNORE INTO dividends"
     "(date, symbol, dividend) "
     "VALUES ('{date}','{symbol}','{dividend}')")

insert_entities_sql = \
    ("INSERT IGNORE INTO entities"
     "(name, symbol, asset_type, sector) "
     "VALUES ('{name}','{symbol}','{asset_type}', '{sector}')")

delete_entities_single_sql = \
    ("DELETE FROM entities WHERE symbol = '{symbol}'")
    
insert_splits_sql = \
    ("INSERT IGNORE INTO splits"
     "(record_date, distribution_date, symbol, multiplier) "
     "VALUES ('{record_date}', '{distribution_date}', '{symbol}', '{multiplier}')")

insert_acquisitions_sql = \
    ("INSERT IGNORE INTO acquisitions"
     "(date, symbol, acquirer, conversion_ratio) "
     "VALUES ('{date}','{symbol}', '{acquirer}', '{conversion_ratio}')")

drop_splits_table_sql = "DROP TABLE IF EXISTS splits"
drop_entities_table_sql = "DROP TABLE IF EXISTS entities"

#gen_summary

drop_summary_table_sql = "DROP TABLE IF EXISTS summary"

create_summary_table_sql = \
    ("CREATE TABLE IF NOT EXISTS summary ("
    "symbol VARCHAR(4) NOT NULL, "
    "name VARCHAR(100) NOT NULL, "
    "current_shares INT NOT NULL, "
    "cost_basis DECIMAL(13, 2) NOT NULL, "
    "first_purchase_date DATE NOT NULL, "
    "last_purchase_date DATE NOT NULL, "
    "total_dividend DECIMAL(13, 2), "
    "dividend_yield DECIMAL(3, 2), "
    "PRIMARY KEY (symbol, name))")

insert_summary_sql = \
    ("INSERT INTO summary"
     "(symbol, name, current_shares, cost_basis, "
     "first_purchase_date, last_purchase_date, total_dividend, dividend_yield) "
     "VALUES ('{symbol}','{name}','{current_shares}','{cost_basis}',"
             "'{first_purchase_date}','{last_purchase_date}',"
             "'{total_dividend}', '{dividend_yield}') " 
     "ON DUPLICATE KEY UPDATE current_shares='{current_shares}'," 
     "cost_basis='{cost_basis}',first_purchase_date='{first_purchase_date}',"
     "last_purchase_date='{last_purchase_date}',total_dividend='{total_dividend}',"
     "dividend_yield='{dividend_yield}'")

# base_summary_query = \
#     ("SELECT t1.name, t1.symbol, t1.current_shares, t2.total_dividend FROM "
#         "(SELECT entities.name, trades.symbol, "
#         "SUM(COALESCE(CASE WHEN trades.action='buy' "
#                         "THEN trades.num_shares END, 0)) - "
#         "SUM(COALESCE(CASE WHEN trades.action='sell' "
#                         "THEN trades.num_shares END, 0)) "
#         "current_shares FROM trades INNER JOIN entities ON "
#         "entities.symbol = trades.symbol GROUP BY entities.name, trades.symbol "
#         "HAVING current_shares > 0 ORDER BY trades.symbol) AS t1 "
#         "LEFT JOIN "
#         "(SELECT dividends.symbol, SUM(dividends.dividend) total_dividend FROM "
#         "dividends GROUP BY dividends.symbol) AS t2 "
#     "ON t1.symbol=t2.symbol ORDER BY t1.name")
# base_summary_columns = ['Name', 'Symbol', 'CurrentShares', 'TotalDividend']
    
stocks_with_sales_query = \
    ("SELECT t1.symbol, t1.bought, t2.sold, t1.bought-t2.sold as remaining FROM "
        "(SELECT symbol, sum(num_shares) as bought FROM trades WHERE action='buy' "
        "GROUP BY symbol order by symbol) t1, "
        "(SELECT symbol, sum(num_shares) as sold FROM trades WHERE action='sell' "
        "GROUP BY symbol order by symbol) t2 "
    "WHERE t1.symbol=t2.symbol AND t1.bought-t2.sold > 0")
stocks_with_sales_columns = ['Symbol', 'Bought', 'Sold', 'Remaining']

all_trades_query = "SELECT * FROM trades"
all_trades_columns = ['Date', 'Symbol', 'Action', 
                      'NumShares', 'PricePerShare','TotalPrice']

splits_query = "SELECT * FROM splits"
splits_columns = ['Record_Date', 'Distribution_Date', 'Symbol', 'Multiplier']

acquisitions_query = "SELECT * FROM acquisitions"
acquisitions_columns = ['Date', 'Symbol', 'Acquirer', 'Conversion_Ratio']

read_entities_table_query = "SELECT * FROM entities"
read_entities_table_columns = ['Name', 'Symbol', 'Asset Type', 'Sector']

### Master Log Summary Method ###
master_log_buys_query = \
    "SELECT date, symbol, action, num_shares FROM trades WHERE action='buy'"
master_log_buys_columns = ['Date', 'Symbol', 'Action', 'Quantity']

master_log_sells_query = \
    "SELECT date, symbol, action, num_shares FROM trades WHERE action='sell'"
master_log_sells_columns = ['Date', 'Symbol', 'Action', 'Quantity']

master_log_dividends_query = \
    "SELECT date, symbol, 'dividend' as 'action', dividend FROM dividends"
master_log_dividends_columns = ['Date', 'Symbol', 'Action', 'Dividend']
                           
master_log_splits_query = \
    "SELECT distribution_date as 'date', symbol, 'split' as 'action', multiplier FROM splits"
master_log_splits_columns = ['Date', 'Symbol', 'Action', 'Multiplier']

master_log_acquisitions_query = \
    "SELECT date, symbol, acquirer, 'acquisition' as 'action', conversion_ratio FROM acquisitions"
master_log_acquisitions_columns = ['Date', 'Symbol', 'Acquirer', 'Action', 'Multiplier']

# Get asset full name and symbol from entities table
asset_name_query = "SELECT symbol,name FROM entities"
asset_name_columns = ['Symbol', 'Name']

read_summary_table_query = "SELECT * FROM summary"
read_summary_table_columns = ['Symbol', 'Name', 'Quantity', 'Cost Basis',
                              'First Purchase Date', 'Last Purchase Date', 
                              'Total Dividend', 'Dividend Yield']
                              
                              
# HistoryHelper - assets_history table
create_assets_history_table_sql = \
    ("CREATE TABLE IF NOT EXISTS assets_history ("
    "date DATE NOT NULL, "
    "symbol VARCHAR(4) NOT NULL, "
    "quantity INT NOT NULL, "
    "closing_price DECIMAL(13, 2) NOT NULL, "
    "value DECIMAL(13, 2) NOT NULL, "
    "PRIMARY KEY (date, symbol))")
    
insert_ignore_assets_history_sql = \
    ("INSERT IGNORE INTO assets_history"
     "(date, symbol, quantity, closing_price, value) "
     "VALUES ('{date}','{symbol}', '{quantity}', '{closing_price}', '{value}')")
    
insert_update_assets_history_sql = \
    ("INSERT INTO assets_history"
     "(date, symbol, quantity, closing_price, value) "
     "VALUES ('{date}','{symbol}', '{quantity}', '{closing_price}', '{value}') "
     "ON DUPLICATE KEY UPDATE "
     "date='{date}', symbol='{symbol}', quantity='{quantity}', "
     "closing_price='{closing_price}', value='{value}'")
    
read_assets_history_query = "SELECT * FROM assets_history"
read_assets_history_columns = ['Date', 'Symbol', 'Quantity', 'ClosingPrice', 'Value']

#HistoryHelper - portfolio_history table
create_portfolio_history_table_sql = \
    ("CREATE TABLE IF NOT EXISTS portfolio_history ("
    "date DATE NOT NULL, "
    "value DECIMAL(13, 2) NOT NULL, "
    "PRIMARY KEY (date))")
    
insert_ignore_portfolio_history_sql = \
    ("INSERT IGNORE INTO portfolio_history"
     "(date, value) VALUES ('{date}','{value}')")
    
insert_update_portfolio_history_sql = \
    ("INSERT INTO portfolio_history"
     "(date, value) VALUES ('{date}','{value}') "
     "ON DUPLICATE KEY UPDATE date='{date}', value='{value}'")
    
read_portfolio_history_query = "SELECT * FROM portfolio_history"
read_portfolio_history_columns = ['Date', 'Value']

# HistoryHelper - assets_hypothetical_history table
create_assets_hypothetical_history_table_sql = \
    ("CREATE TABLE IF NOT EXISTS assets_hypothetical_history ("
    "date DATE NOT NULL, "
    "symbol VARCHAR(4) NOT NULL, "
    "quantity INT NOT NULL, "
    "closing_price DECIMAL(13, 2) NOT NULL, "
    "value DECIMAL(13, 2) NOT NULL, "
    "PRIMARY KEY (date, symbol))")
    
insert_ignore_assets_hypothetical_history_sql = \
    ("INSERT IGNORE INTO assets_hypothetical_history"
     "(date, symbol, quantity, closing_price, value) "
     "VALUES ('{date}','{symbol}','{quantity}','{closing_price}','{value}')")
    
insert_update_assets_hypothetical_history_sql = \
    ("INSERT INTO assets_hypothetical_history"
     "(date, symbol, quantity, closing_price, value) "
     "VALUES ('{date}','{symbol}', '{quantity}','{closing_price}','{value}') "
     "ON DUPLICATE KEY UPDATE "
     "date='{date}',symbol='{symbol}',quantity='{quantity}', "
     "closing_price='{closing_price}',value='{value}'")
    
read_assets_hypothetical_history_query = "SELECT * FROM assets_hypothetical_history"
read_assets_hypothetical_history_columns = ['Date', 'Symbol', 'Quantity', 'ClosingPrice', 'Value']

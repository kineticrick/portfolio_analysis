
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
    "date DATE NOT NULL, "
    "symbol VARCHAR(4) NOT NULL, "
    "multiplier INT NOT NULL, "
    "PRIMARY KEY (date, symbol, multiplier))")

create_entities_table_sql = \
    ("CREATE TABLE IF NOT EXISTS entities ("
     "name VARCHAR(100) NOT NULL, "
     "symbol VARCHAR(4) NOT NULL, "
     "asset_type VARCHAR(100) NOT NULL, "
     "sector VARCHAR(100) NOT NULL, "
     "PRIMARY KEY (name, symbol, asset_type, sector))")
    
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
    
insert_splits_sql = \
    ("INSERT IGNORE INTO splits"
     "(date, symbol, multiplier) "
     "VALUES ('{date}','{symbol}','{multiplier}')")
    
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
    "has_dividend BOOLEAN NOT NULL, "
    "total_dividend DECIMAL(13, 2), "
    "PRIMARY KEY (symbol, name))")

insert_summary_sql = \
    ("INSERT INTO summary"
     "(symbol, name, current_shares, cost_basis, "
     "first_purchase_date, last_purchase_date, has_dividend, total_dividend) "
     "VALUES ('{symbol}','{name}','{current_shares}',{cost_basis},"
             "'{first_purchase_date}','{last_purchase_date}',"
             "'{has_dividend}','{total_dividend}') " 
     "ON DUPLICATE KEY UPDATE current_shares='{current_shares}'," 
     "cost_basis={cost_basis},first_purchase_date='{first_purchase_date}',"
     "last_purchase_date='{last_purchase_date}',has_dividend='{has_dividend}',"
     "total_dividend='{total_dividend}'")

base_summary_query = \
    ("SELECT t1.name, t1.symbol, t1.current_shares, t2.total_dividend FROM "
        "(SELECT entities.name, trades.symbol, "
        "SUM(COALESCE(CASE WHEN trades.action='buy' "
                        "THEN trades.num_shares END, 0)) - "
        "SUM(COALESCE(CASE WHEN trades.action='sell' "
                        "THEN trades.num_shares END, 0)) "
        "current_shares FROM trades INNER JOIN entities ON "
        "entities.symbol = trades.symbol GROUP BY entities.name, trades.symbol "
        "HAVING current_shares > 0 ORDER BY trades.symbol) AS t1 "
        "LEFT JOIN "
        "(SELECT dividends.symbol, SUM(dividends.dividend) total_dividend FROM "
        "dividends GROUP BY dividends.symbol) AS t2 "
    "ON t1.symbol=t2.symbol ORDER BY t1.name")
base_summary_columns = ['Name', 'Symbol', 'CurrentShares', 'TotalDividend']
    
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
splits_columns = ['Date', 'Symbol', 'Multiplier']


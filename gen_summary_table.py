#!/usr/bin/env python
import numpy as np
import pandas as pd

from decimal import Decimal
from mysqldb import MysqlDB

from dbcfg import *
from sql import *
from pandas_helpers import * 

all_trades_df = mysql_to_df(all_trades_query,
                            all_trades_columns, dbcfg)

all_buys_df = all_trades_df[(all_trades_df['Action'] == "buy")]

# print_full(all_buys_df)
base_cost_basis_df = all_buys_df.groupby('Symbol')[['TotalPrice']].sum()

# print_full(base_cost_basis_df)
sales_df = mysql_to_df(stocks_with_sales_query, 
                       stocks_with_sales_columns, dbcfg)

cost_basis_sold_dict = {}
for _, row in sales_df.iterrows():
    symbol, num_sold = row['Symbol'], float(row['Sold'])
    
    entry_price_per_share = all_buys_df[
        (all_buys_df['Symbol'] == symbol)].sort_values(by='Date')\
            ['PricePerShare'].iloc[0]
    
    entry_price_per_share = float(entry_price_per_share)
    
    total_cost_basis_sold = num_sold * entry_price_per_share

    cost_basis_sold_dict[symbol] = total_cost_basis_sold

for symbol, cost_basis_sold in cost_basis_sold_dict.items():
    base_cost_basis_df.loc[symbol]['TotalPrice'] = \
        base_cost_basis_df.loc[symbol]['TotalPrice'] - Decimal(cost_basis_sold)

base_summary_df = mysql_to_df(base_summary_query, 
                              base_summary_columns, dbcfg)
# print_full(base_summary_df)
merged_df = pd.merge(left=base_summary_df, right=base_cost_basis_df, on='Symbol')
merged_df = merged_df.rename(columns={'TotalPrice':'CostBasis'})
# print_full(merged_df)

merged_df['HasDividend'] = np.where(merged_df['TotalDividend'] > 0, 1, 0)

first_purchase_date_df = \
    all_buys_df.sort_values(by=['Symbol','Date']).groupby('Symbol').first()[['Date']]
first_purchase_date_df  = first_purchase_date_df.rename(columns={'Date': 'FirstPurchaseDate'})
last_purchase_date_df = \
    all_buys_df.sort_values(by=['Symbol','Date']).groupby('Symbol').last()[['Date']]
last_purchase_date_df  = last_purchase_date_df.rename(columns={'Date': 'LastPurchaseDate'})

merged_df = pd.merge(left=merged_df, right=first_purchase_date_df, on='Symbol')
merged_df = pd.merge(left=merged_df, right=last_purchase_date_df, on='Symbol')
merged_df['TotalDividend'] = merged_df['TotalDividend'].fillna(0)

# Process any splits, after all other work (namely, cost basis) has been done
splits_df = mysql_to_df(splits_query,
                            splits_columns, dbcfg)
for _, row in splits_df.iterrows(): 
    symbol = row['Symbol']
    multiplier = int(row['Multiplier'])
    
    merged_df.loc[merged_df['Symbol'] == symbol, 'CurrentShares'] = \
        merged_df.loc[merged_df['Symbol'] == symbol, 'CurrentShares'] * 4
    
with MysqlDB(dbcfg) as db:
    print(drop_summary_table_sql)
    db.execute(drop_summary_table_sql)
    
    print(create_summary_table_sql)
    db.execute(create_summary_table_sql)
    
    for index, row in merged_df.iterrows(): 
        insertion_dict = {}
        insertion_dict['symbol'] = row['Symbol']
        insertion_dict['name'] = row['Name']
        insertion_dict['current_shares'] = row['CurrentShares']
        insertion_dict['cost_basis'] = row['CostBasis']
        insertion_dict['first_purchase_date'] = row['FirstPurchaseDate']
        insertion_dict['last_purchase_date'] = row['LastPurchaseDate']
        insertion_dict['has_dividend'] = row['HasDividend']
        insertion_dict['total_dividend'] = row['TotalDividend']
        
        sql = insert_summary_sql.format(**insertion_dict)
        print(sql)
        db.execute(sql)
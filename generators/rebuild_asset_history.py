#!/usr/bin/env python3
"""One-time rebuild of asset-derived history after the per-account schema change.

assets_history changed from PRIMARY KEY (date, symbol) to
(date, symbol, account_type). This script regenerates the affected stored
tables from transactions (prices are cached):

  1. assets_history            (DROP + recreate with new schema, then rebuild)
  2. portfolio_history         (TRUNCATE + rebuild; sums assets_history per date)
  3. assets_hypothetical_history (TRUNCATE + rebuild; derives from assets_history)

Dimension tables (sector/asset_type/account_type/geography) are NOT rebuilt —
they recompute from transactions and are already correct.

Run once after deploying the schema change:

    source venv/bin/activate
    python generators/rebuild_asset_history.py
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from libraries.db import dbcfg, MysqlDB
from libraries.db.mysql_helpers import mysql_cache_evict
from libraries.globals import MYSQL_CACHE_HISTORY_TAG
from libraries.HistoryHandlers import (AssetHistoryHandler,
                                       PortfolioHistoryHandler,
                                       AssetHypotheticalHistoryHandler)


def rebuild_asset_history():
    # Evict cached reads up front so handlers see live (post-DDL) table state.
    mysql_cache_evict(MYSQL_CACHE_HISTORY_TAG)

    # 1. assets_history: drop the old-schema table; constructing the handler
    #    recreates it (new schema, via gen_table) and, seeing it empty, rebuilds
    #    the full per-account history.
    print("Rebuilding assets_history (per-account)...")
    with MysqlDB(dbcfg) as db:
        db.execute("DROP TABLE IF EXISTS assets_history")
    AssetHistoryHandler()

    # 2. portfolio_history derives from assets_history.
    print("Rebuilding portfolio_history...")
    with MysqlDB(dbcfg) as db:
        db.execute("TRUNCATE TABLE portfolio_history")
    PortfolioHistoryHandler()

    # 3. assets_hypothetical_history derives from assets_history.
    print("Rebuilding assets_hypothetical_history...")
    with MysqlDB(dbcfg) as db:
        db.execute("TRUNCATE TABLE assets_hypothetical_history")
    AssetHypotheticalHistoryHandler()

    mysql_cache_evict(MYSQL_CACHE_HISTORY_TAG)
    print("✓ Rebuild complete; history cache evicted.")


if __name__ == '__main__':
    rebuild_asset_history()

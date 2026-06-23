# Per-account assets_history Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store `assets_history` per `(date, symbol, account_type)` so a symbol held in two accounts no longer loses a row, and rebuild the derived history tables.

**Architecture:** Clean the leaked `'Agnostic'` account label at its source (`gen_hist_quantities_mult`), add `account_type` to the `assets_history` schema/primary key, insert per-account rows, expose a per-symbol aggregation seam so existing consumers are unchanged, and provide a one-time rebuild script. Foundation only — no Assets-tab UI.

**Tech Stack:** Python 3.13, pandas, MySQL (mysql.connector via `MysqlDB`), unittest, yfinance (cached).

## Global Constraints

- Tests use `unittest`, run via `python -m unittest <module> -v`. NOT pytest.
- Real-DB / yfinance-backed tests are acceptable (repo convention); bound them with a recent `start_date` where possible. Prices are disk-cached.
- `account_type` valid values: `'Discretionary'`, `'Retirement'`. Split/acquisition events are `'Agnostic'` and apply to every account.
- `assets_history` column order after change: `date, symbol, account_type, quantity, cost_basis, closing_price, value, percent_return`. `read_assets_history_columns` maps positionally (via `mysql_to_df`), so its order MUST match.
- **The rebuild is MANDATORY after this change** — the schema changes, so the dashboard cannot write/read `assets_history` until `generators/rebuild_asset_history.py` has been run once. This is not optional.
- Activate the venv before running anything: `source venv/bin/activate`.
- Commit message trailers (every commit), exactly:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c
  ```
- Work on branch `assets-history-per-account` (already checked out). Do NOT switch branches.

---

## File Structure

- `libraries/helpers.py` — stamp true account in `gen_hist_quantities_mult`; add pure `aggregate_assets_history_by_symbol`.
- `libraries/db/sql.py` — `assets_history` schema (`account_type` + PK), insert SQL constants, `read_assets_history_columns`.
- `libraries/HistoryHandlers/AssetHistoryHandler.py` — pure `build_assets_history_rows`; per-account insert in `set_history`.
- `visualization/dash/DashboardHandler.py` — expose `assets_history_by_account_df` + per-symbol `assets_history_df`.
- `libraries/HistoryHandlers/AssetHypotheticalHistoryHandler.py` — aggregate to per-symbol when it fetches its own asset history.
- `generators/rebuild_asset_history.py` — new one-time rebuild script.
- `README.md` — document the mandatory rebuild step.
- `tests/libraries/test_assets_history.py` — new; pure tests (aggregate, build rows, schema consistency, rebuild import).
- `tests/libraries/test_account_filtering.py` — append real-DB tests (clean labels, aggregate-on-real-history).

---

### Task 1: Clean the account label at the source

**Files:**
- Modify: `libraries/helpers.py` (`gen_hist_quantities_mult`, the loop around lines 343-353)
- Test: `tests/libraries/test_account_filtering.py` (append)

**Interfaces:**
- Produces: `gen_assets_historical_value(...)` output `AccountType` column now contains only `'Discretionary'`/`'Retirement'` (never `'Agnostic'`).

- [ ] **Step 1: Write the failing test**

Append to `tests/libraries/test_account_filtering.py`:

```python
class TestAccountLabelCleaning(unittest.TestCase):
    def test_value_rows_have_clean_account_labels(self):
        from libraries.helpers import gen_assets_historical_value
        df = gen_assets_historical_value(cadence="daily", start_date="2026-01-01")
        self.assertIn("AccountType", df.columns)
        labels = set(df["AccountType"].unique())
        self.assertTrue(labels.issubset({"Discretionary", "Retirement"}),
                        f"leaked labels present: {labels}")

    def test_account_dimension_has_no_agnostic_bucket(self):
        from libraries.helpers import gen_aggregated_historical_value
        agg = gen_aggregated_historical_value("AccountType", start_date="2026-01-01")
        self.assertNotIn("Agnostic", set(agg["AccountType"].unique()))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.test_account_filtering.TestAccountLabelCleaning -v`
Expected: FAIL — `Agnostic` is present in the labels (the leak).

- [ ] **Step 3: Stamp the true account on each series**

In `libraries/helpers.py`, in `gen_hist_quantities_mult`, the loop currently reads:

```python
        symbol_quantities_df = gen_hist_quantities(symbol_event_log_df, 
                                                   cadence=cadence,
                                                   expand_chronology=expand_chronology)
        quantities_df = pd.concat([quantities_df, symbol_quantities_df])
```

Change it to stamp the series' real account (overwriting any leaked `'Agnostic'` label) before concatenating:

```python
        symbol_quantities_df = gen_hist_quantities(symbol_event_log_df, 
                                                   cadence=cadence,
                                                   expand_chronology=expand_chronology)
        # The per-event AccountType ffills 'Agnostic' (splits/acquisitions) across a
        # series; overwrite with this series' true account so every row is cleanly
        # labeled. Required for the (date, symbol, account_type) primary key, and it
        # also removes the spurious 'Agnostic' bucket from the AccountType dimension.
        symbol_quantities_df['AccountType'] = account_type
        quantities_df = pd.concat([quantities_df, symbol_quantities_df])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.test_account_filtering.TestAccountLabelCleaning -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the broader real-DB suite to confirm no regression**

Run: `python -m unittest tests.libraries.test_account_filtering tests.libraries.test_helpers -v`
Expected: OK (the Sector `Disc + Ret == full` invariant and value-weighted tests still pass — only labels changed, not values).

- [ ] **Step 6: Commit**

```bash
git add libraries/helpers.py tests/libraries/test_account_filtering.py
git commit -m "Stamp true account on each quantity series (drop leaked Agnostic)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 2: `assets_history` schema gains `account_type`

**Files:**
- Modify: `libraries/db/sql.py` (lines 157-182: create SQL, insert SQL constants, read columns)
- Test: `tests/libraries/test_assets_history.py` (create)

**Interfaces:**
- Produces: `assets_history` table keyed `(date, symbol, account_type)`; `read_assets_history_columns = ['Date','Symbol','AccountType','Quantity','CostBasis','ClosingPrice','Value','PercentReturn']`.

- [ ] **Step 1: Write the failing test**

Create `tests/libraries/test_assets_history.py`:

```python
import unittest

from libraries.db import sql


class TestAssetsHistorySchema(unittest.TestCase):
    def test_create_sql_has_account_type_in_pk(self):
        create = sql.create_assets_history_table_sql
        self.assertIn("account_type", create)
        self.assertIn("PRIMARY KEY (date, symbol, account_type)", create)

    def test_read_columns_match_table_column_order(self):
        # Column names in the CREATE statement, before PRIMARY KEY, must map
        # 1:1 (and in order) to read_assets_history_columns, because mysql_to_df
        # assigns column names positionally to `SELECT *`.
        create = sql.create_assets_history_table_sql
        body = create[create.index("(") + 1: create.index("PRIMARY KEY")]
        col_names = [seg.strip().split()[0] for seg in body.split(",")
                     if seg.strip()]
        mapping = {
            "date": "Date", "symbol": "Symbol", "account_type": "AccountType",
            "quantity": "Quantity", "cost_basis": "CostBasis",
            "closing_price": "ClosingPrice", "value": "Value",
            "percent_return": "PercentReturn",
        }
        expected = [mapping[c] for c in col_names]
        self.assertEqual(expected, sql.read_assets_history_columns)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.test_assets_history.TestAssetsHistorySchema -v`
Expected: FAIL — `account_type` not in the create SQL / columns mismatch.

- [ ] **Step 3: Update the schema, insert constants, and read columns**

In `libraries/db/sql.py`, replace the `assets_history` block (lines 157-182) with:

```python
create_assets_history_table_sql = \
    ("CREATE TABLE IF NOT EXISTS assets_history ("
    "date DATE NOT NULL, "
    "symbol VARCHAR(4) NOT NULL, "
    "account_type VARCHAR(100) NOT NULL, "
    "quantity INT NOT NULL, "
    "cost_basis DECIMAL(13, 2) NOT NULL, "
    "closing_price DECIMAL(13, 2) NOT NULL, "
    "value DECIMAL(13, 2) NOT NULL, "
    "percent_return DECIMAL(13, 2) NOT NULL, "
    "PRIMARY KEY (date, symbol, account_type))")
    
insert_ignore_assets_history_sql = \
    ("INSERT IGNORE INTO assets_history"
     "(date, symbol, account_type, quantity, cost_basis, closing_price, value, percent_return) "
     "VALUES ('{date}','{symbol}', '{account_type}', '{quantity}', '{cost_basis}', '{closing_price}', '{value}', '{percent_return}')")
    
insert_update_assets_history_sql = \
    ("INSERT INTO assets_history"
     "(date, symbol, account_type, quantity, cost_basis, closing_price, value, percent_return) "
     "VALUES ('{date}','{symbol}', '{account_type}', '{quantity}', '{cost_basis}', '{closing_price}', '{value}', '{percent_return}') "
     "ON DUPLICATE KEY UPDATE "
     "date='{date}', symbol='{symbol}', account_type='{account_type}', quantity='{quantity}', "
     "cost_basis='{cost_basis}', closing_price='{closing_price}', value='{value}', percent_return='{percent_return}'")
    
read_assets_history_query = "SELECT * FROM assets_history"
read_assets_history_columns = ['Date', 'Symbol', 'AccountType', 'Quantity', 'CostBasis', 'ClosingPrice', 'Value', 'PercentReturn']
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.test_assets_history.TestAssetsHistorySchema -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add libraries/db/sql.py tests/libraries/test_assets_history.py
git commit -m "Add account_type to assets_history schema and read columns

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 3: `aggregate_assets_history_by_symbol` helper

**Files:**
- Modify: `libraries/helpers.py` (add function next to `gen_assets_historical_value`)
- Test: `tests/libraries/test_assets_history.py` (append)

**Interfaces:**
- Produces: `aggregate_assets_history_by_symbol(df) -> pd.DataFrame` with columns `Date, Symbol, Quantity, CostBasis, ClosingPrice, Value, PercentReturn` (no `AccountType`); one row per `(Date, Symbol)`. Idempotent on a frame already at per-symbol grain. Empty in → returned unchanged.

- [ ] **Step 1: Write the failing test**

Append to `tests/libraries/test_assets_history.py`:

```python
import datetime

import pandas as pd

from libraries.helpers import aggregate_assets_history_by_symbol


class TestAggregateBySymbol(unittest.TestCase):
    def _per_account(self):
        d = datetime.date(2026, 1, 2)
        return pd.DataFrame({
            "Date": [d, d, d],
            "Symbol": ["DUP", "DUP", "SOLO"],
            "AccountType": ["Discretionary", "Retirement", "Discretionary"],
            "Quantity": [10, 5, 3],
            "CostBasis": [100.0, 60.0, 30.0],
            "ClosingPrice": [12.0, 12.0, 8.0],
            "Value": [120.0, 60.0, 24.0],
            "PercentReturn": [20.0, 0.0, -20.0],
        })

    def test_multi_account_symbol_collapses_to_one_row(self):
        out = aggregate_assets_history_by_symbol(self._per_account())
        dup = out[out["Symbol"] == "DUP"]
        self.assertEqual(len(dup), 1)
        row = dup.iloc[0]
        self.assertEqual(row["Quantity"], 15)          # 10 + 5
        self.assertAlmostEqual(row["CostBasis"], 160.0)  # 100 + 60
        self.assertAlmostEqual(row["Value"], 180.0)      # 120 + 60
        self.assertAlmostEqual(row["ClosingPrice"], 12.0)  # identical, 'first'
        # return recomputed from summed totals: (180 - 160) / 160 * 100 = 12.5
        self.assertAlmostEqual(row["PercentReturn"], 12.5)
        self.assertNotIn("AccountType", out.columns)

    def test_single_account_symbol_unchanged(self):
        out = aggregate_assets_history_by_symbol(self._per_account())
        solo = out[out["Symbol"] == "SOLO"].iloc[0]
        self.assertEqual(solo["Quantity"], 3)
        self.assertAlmostEqual(solo["Value"], 24.0)

    def test_idempotent_on_per_symbol_frame(self):
        once = aggregate_assets_history_by_symbol(self._per_account())
        twice = aggregate_assets_history_by_symbol(once)
        self.assertEqual(len(once), len(twice))

    def test_zero_cost_basis_guarded(self):
        d = datetime.date(2026, 1, 2)
        df = pd.DataFrame({
            "Date": [d], "Symbol": ["Z"], "AccountType": ["Discretionary"],
            "Quantity": [1], "CostBasis": [0.0], "ClosingPrice": [5.0],
            "Value": [5.0], "PercentReturn": [0.0]})
        out = aggregate_assets_history_by_symbol(df)
        self.assertEqual(out.iloc[0]["PercentReturn"], 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.test_assets_history.TestAggregateBySymbol -v`
Expected: FAIL — `ImportError: cannot import name 'aggregate_assets_history_by_symbol'`.

- [ ] **Step 3: Implement the helper**

In `libraries/helpers.py`, after `gen_assets_historical_value` (before `gen_aggregated_historical_value`), add:

```python
def aggregate_assets_history_by_symbol(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse per-(date, symbol, account) asset history to per-(date, symbol).

    Sums Quantity/CostBasis/Value, keeps ClosingPrice (identical per ticker/date),
    and recomputes PercentReturn from the summed totals. Idempotent: a frame
    already at per-symbol grain passes through unchanged. Used by readers that
    want per-symbol totals while the stored table keeps per-account rows.
    """
    if df.empty:
        return df
    out = df.groupby(['Date', 'Symbol'], as_index=False).agg(
        Quantity=('Quantity', 'sum'),
        CostBasis=('CostBasis', 'sum'),
        ClosingPrice=('ClosingPrice', 'first'),
        Value=('Value', 'sum'),
    )
    out['PercentReturn'] = out.apply(
        lambda r: (r['Value'] - r['CostBasis']) / r['CostBasis'] * 100
        if r['CostBasis'] else 0.0, axis=1)
    out[['CostBasis', 'ClosingPrice', 'Value', 'PercentReturn']] = \
        out[['CostBasis', 'ClosingPrice', 'Value', 'PercentReturn']].round(2)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.test_assets_history.TestAggregateBySymbol -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add libraries/helpers.py tests/libraries/test_assets_history.py
git commit -m "Add aggregate_assets_history_by_symbol helper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 4: Insert per-account rows in `AssetHistoryHandler.set_history`

**Files:**
- Modify: `libraries/HistoryHandlers/AssetHistoryHandler.py` (add module-level `build_assets_history_rows`; update `set_history` SQL + values, lines 61-84)
- Test: `tests/libraries/test_assets_history.py` (append)

**Interfaces:**
- Consumes: clean `AccountType` labels (Task 1); `account_type` column (Task 2).
- Produces: `build_assets_history_rows(df) -> list[tuple]` — 8-field tuples `(Date, Symbol, AccountType, Quantity, CostBasis, ClosingPrice, Value, PercentReturn)`, one per input row (no collapsing).

- [ ] **Step 1: Write the failing test**

Append to `tests/libraries/test_assets_history.py`:

```python
from libraries.HistoryHandlers.AssetHistoryHandler import build_assets_history_rows


class TestBuildAssetsHistoryRows(unittest.TestCase):
    def test_one_tuple_per_row_with_account_type(self):
        d = datetime.date(2026, 1, 2)
        df = pd.DataFrame({
            "Date": [d, d],
            "Symbol": ["DUP", "DUP"],
            "AccountType": ["Discretionary", "Retirement"],
            "Quantity": [10, 5],
            "CostBasis": [100.0, 60.0],
            "ClosingPrice": [12.0, 12.0],
            "Value": [120.0, 60.0],
            "PercentReturn": [20.0, 0.0],
        })
        rows = build_assets_history_rows(df)
        self.assertEqual(len(rows), 2)            # both accounts preserved
        self.assertTrue(all(len(t) == 8 for t in rows))
        self.assertEqual({t[2] for t in rows}, {"Discretionary", "Retirement"})
        # field order: (Date, Symbol, AccountType, Quantity, CostBasis,
        #               ClosingPrice, Value, PercentReturn)
        self.assertEqual(rows[0][1], "DUP")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.test_assets_history.TestBuildAssetsHistoryRows -v`
Expected: FAIL — `ImportError: cannot import name 'build_assets_history_rows'`.

- [ ] **Step 3: Add the row builder and use it in `set_history`**

In `libraries/HistoryHandlers/AssetHistoryHandler.py`, add a module-level function (after the imports, before the class):

```python
def build_assets_history_rows(assets_df):
    """Per-account insert tuples for assets_history, one per input row:
    (date, symbol, account_type, quantity, cost_basis, closing_price,
     value, percent_return)."""
    return [
        (row['Date'], row['Symbol'], row['AccountType'], row['Quantity'],
         row['CostBasis'], row['ClosingPrice'], row['Value'],
         row['PercentReturn'])
        for _, row in assets_df.iterrows()
    ]
```

Then replace the SQL + values block in `set_history` (lines 63-84) with:

```python
        with MysqlDB(dbcfg) as db:
            if overwrite:
                # Use REPLACE INTO for overwrite
                sql = """REPLACE INTO assets_history
                         (date, symbol, account_type, quantity, cost_basis, closing_price, value, percent_return)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
            else:
                # Use INSERT IGNORE for append-only
                sql = """INSERT IGNORE INTO assets_history
                         (date, symbol, account_type, quantity, cost_basis, closing_price, value, percent_return)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""

            # One row per (date, symbol, account_type) — no collapsing, no drops.
            values = build_assets_history_rows(assets_historical_data_df)

            if values:
                db.cursor.executemany(sql, values)
                print(f"✓ Batch inserted {len(values)} asset history rows")
```

(The `column_conversion_map` dict above this block is unused and can be left as-is.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.test_assets_history.TestBuildAssetsHistoryRows -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add libraries/HistoryHandlers/AssetHistoryHandler.py tests/libraries/test_assets_history.py
git commit -m "Insert assets_history per (date, symbol, account_type)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 5: Per-symbol seam for existing readers

**Files:**
- Modify: `visualization/dash/DashboardHandler.py` (import line ~14; init lines 52-55)
- Modify: `libraries/HistoryHandlers/AssetHypotheticalHistoryHandler.py` (the `assets_history_df is None` branch, ~lines 55-61)
- Test: `tests/libraries/test_account_filtering.py` (append)

**Interfaces:**
- Consumes: `aggregate_assets_history_by_symbol` (Task 3).
- Produces: `DashboardHandler.assets_history_df` is per-symbol totals (unchanged contract); `DashboardHandler.assets_history_by_account_df` is per-account (new).

- [ ] **Step 1: Write the failing test**

Append to `tests/libraries/test_account_filtering.py`:

```python
class TestPerSymbolSeam(unittest.TestCase):
    def test_aggregate_real_history_is_unique_per_symbol(self):
        from libraries.HistoryHandlers import AssetHistoryHandler
        from libraries.helpers import aggregate_assets_history_by_symbol
        hist = AssetHistoryHandler().history_df
        agg = aggregate_assets_history_by_symbol(hist)
        dups = int(agg.duplicated(subset=["Date", "Symbol"]).sum())
        self.assertEqual(dups, 0)
        self.assertNotIn("AccountType", agg.columns)
```

- [ ] **Step 2: Run test to verify it passes (sanity) or fails on import**

Run: `python -m unittest tests.libraries.test_account_filtering.TestPerSymbolSeam -v`
Expected: PASS once Task 3 is merged (the helper already exists and yields unique per-symbol rows on real data; this test guards that the seam stays correct). If it errors on import, Task 3 is missing — stop and report.

- [ ] **Step 3: Wire the seam into `DashboardHandler`**

In `visualization/dash/DashboardHandler.py`, extend the helpers import (line ~14) to add `aggregate_assets_history_by_symbol`:

```python
from libraries.helpers import (get_portfolio_current_value, add_asset_info,
                               gen_aggregated_historical_value,
                               aggregate_assets_history_by_symbol)
```

Replace the assets-history wiring (lines 51-55) with:

```python
        # Get and set assets history. The stored table is per-account; expose
        # the faithful per-account frame (for future per-account asset views)
        # AND a per-symbol-aggregated frame that every current consumer uses.
        self.assets_history_by_account_df = ah.history_df
        self.assets_history_df = aggregate_assets_history_by_symbol(ah.history_df)
        portfolio_symbols = self.current_portfolio_summary_df['Symbol'].tolist()
        self.portfolio_assets_history_df = self.assets_history_df.loc[
            self.assets_history_df['Symbol'].isin(portfolio_symbols)]
```

- [ ] **Step 4: Wire the seam into `AssetHypotheticalHistoryHandler`**

In `libraries/HistoryHandlers/AssetHypotheticalHistoryHandler.py`, add to the imports near the top:

```python
from libraries.helpers import aggregate_assets_history_by_symbol
```

Replace the `assets_history_df is None` branch (~lines 55-61) with:

```python
        if assets_history_df is None:
            # Initialize AssetHistoryHandler to ensure that base data is up-to-date
            asset_history_handler = AssetHistoryHandler(self.symbols)
            # Stored history is per-account; this handler works per-symbol.
            self.assets_history_df = aggregate_assets_history_by_symbol(
                asset_history_handler.history_df)
        else:
            self.assets_history_df = assets_history_df
```

- [ ] **Step 5: Run the seam test and the chat/helpers regression**

Run:
```bash
python -m unittest tests.libraries.test_account_filtering tests.libraries.test_helpers tests.libraries.test_assets_history -v
```
Expected: OK. (Full integration against the live per-account table is verified in Task 7.)

- [ ] **Step 6: Commit**

```bash
git add visualization/dash/DashboardHandler.py libraries/HistoryHandlers/AssetHypotheticalHistoryHandler.py tests/libraries/test_account_filtering.py
git commit -m "Expose per-account + per-symbol asset history views

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 6: Rebuild script + README

**Files:**
- Create: `generators/rebuild_asset_history.py`
- Modify: `README.md` (add a "Rebuilding asset history" note)
- Test: `tests/libraries/test_assets_history.py` (append)

**Interfaces:**
- Produces: `generators/rebuild_asset_history.py` exposing `rebuild_asset_history()` (callable; also runnable as `__main__`).

- [ ] **Step 1: Write the failing test**

Append to `tests/libraries/test_assets_history.py`:

```python
import importlib.util
import os


class TestRebuildScript(unittest.TestCase):
    def test_rebuild_module_exposes_callable(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..",
                            "generators", "rebuild_asset_history.py")
        path = os.path.abspath(path)
        self.assertTrue(os.path.exists(path), f"missing: {path}")
        spec = importlib.util.spec_from_file_location("rebuild_asset_history",
                                                      path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)   # import only; does NOT run the rebuild
        self.assertTrue(callable(getattr(mod, "rebuild_asset_history", None)))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.test_assets_history.TestRebuildScript -v`
Expected: FAIL — the script file does not exist yet.

- [ ] **Step 3: Create the rebuild script**

Create `generators/rebuild_asset_history.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.test_assets_history.TestRebuildScript -v`
Expected: PASS (imports the module; does not run the rebuild).

- [ ] **Step 5: Document the rebuild in the README**

In `README.md`, add a subsection under the data/maintenance area (place it near the "Data Import" / generators commands):

```markdown
### Rebuilding asset history (one-time, after the per-account migration)

`assets_history` stores one row per `(date, symbol, account_type)`. After
pulling the change that introduced this schema, run the one-time rebuild once
before starting the dashboard (the schema changed, so the old table must be
regenerated):

```bash
source venv/bin/activate
python generators/rebuild_asset_history.py
```

This regenerates `assets_history`, `portfolio_history`, and
`assets_hypothetical_history` from your transactions (prices are cached). It is
safe to re-run.
```

- [ ] **Step 6: Commit**

```bash
git add generators/rebuild_asset_history.py README.md tests/libraries/test_assets_history.py
git commit -m "Add one-time rebuild script for per-account asset history

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 7: Execute the rebuild and verify (migration + integration)

> **Destructive against the live DB** (regenerable). This task runs the one-time
> rebuild and verifies the result. The controller should run this directly (or
> hand it to the user), not delegate to a fresh subagent.

**Files:** none (operational + verification)

- [ ] **Step 1: Run the rebuild**

Run: `source venv/bin/activate && python generators/rebuild_asset_history.py`
Expected: prints the three "Rebuilding..." lines and `✓ Rebuild complete`. May take minutes (full history regen; prices cached).

- [ ] **Step 2: Verify per-account rows + key uniqueness (real DB)**

Run:
```bash
source venv/bin/activate && python -c "
from libraries.pandas_helpers import mysql_to_df
from libraries.db import dbcfg
from libraries.db.sql import read_assets_history_query, read_assets_history_columns
df = mysql_to_df(read_assets_history_query, read_assets_history_columns, dbcfg, cached=False)
assert 'AccountType' in df.columns, df.columns
dups = int(df.duplicated(subset=['Date','Symbol','AccountType']).sum())
print('duplicate (date,symbol,account_type) keys:', dups)
multi = df.groupby(['Date','Symbol'])['AccountType'].nunique()
syms = sorted(set(df.loc[df['Symbol'].isin(multi[multi>1].reset_index()['Symbol']), 'Symbol']))
print('symbols with >1 account on some date:', syms[:10])
assert dups == 0
print('OK: per-account rows, no duplicate keys')
"
```
Expected: `duplicate ... keys: 0`, a non-empty list of multi-account symbols (e.g. includes QQQ/VGT/VOO), and `OK: ...`.

- [ ] **Step 3: Verify the DashboardHandler seam (real DB)**

Run:
```bash
source venv/bin/activate && python -c "
from visualization.dash.DashboardHandler import DashboardHandler
h = DashboardHandler()
a = h.assets_history_df
b = h.assets_history_by_account_df
assert 'AccountType' not in a.columns, 'assets_history_df should be per-symbol'
assert 'AccountType' in b.columns, 'by_account df should carry AccountType'
assert int(a.duplicated(subset=['Date','Symbol']).sum()) == 0
print('OK: per-symbol assets_history_df, per-account by_account df')
"
```
Expected: `OK: ...`.

- [ ] **Step 4: Full regression**

Run:
```bash
source venv/bin/activate && python -m unittest \
  tests.libraries.test_assets_history \
  tests.libraries.test_account_filtering \
  tests.libraries.test_helpers \
  tests.libraries.test_returns \
  tests.libraries.test_yfinancelib \
  tests.libraries.chat.test_tools \
  tests.libraries.chat.test_engine \
  tests.libraries.chat.test_chart_builders \
  tests.libraries.chat.test_config \
  tests.libraries.chat.test_provider \
  tests.libraries.chat.test_chat_tab_import \
  tests.libraries.chat.test_tools_integration -v 2>&1 | tail -5
```
Expected: OK (all pass).

- [ ] **Step 5: Record completion**

No commit (operational task). Note in the progress ledger that the rebuild ran and the three verifications passed.

---

## Self-Review

**Spec coverage:**
- Account-label cleaning (`gen_hist_quantities_mult`) + AccountType-dimension consequence → Task 1. ✓
- Schema: `account_type` + PK `(date, symbol, account_type)`; read columns positional order → Task 2. ✓
- Per-account insert (no collapse, no drop) → Task 4. ✓
- Per-symbol aggregation seam; `assets_history_df` (per-symbol) + `assets_history_by_account_df` (per-account); hypothetical handler; PortfolioHistoryHandler unchanged → Tasks 3, 5. ✓
- One-time rebuild (DROP+recreate assets_history; TRUNCATE+rebuild portfolio + hypothetical; cache evict) + README → Tasks 6, 7. ✓
- Testing: label cleaning, schema consistency, aggregate math, row builder, per-symbol uniqueness on real data, per-account round-trip + portfolio sanity, full regression → Tasks 1-7. ✓
- Out of scope (Assets-tab UI) → not in any task. ✓

**Type consistency:** `aggregate_assets_history_by_symbol(df) -> df` (Task 3) consumed in Task 5 (DashboardHandler, hypothetical handler) and Task 7 verification. `build_assets_history_rows(df) -> list[tuple]` (Task 4) 8-field order matches the Task 2 SQL column order `(date, symbol, account_type, quantity, cost_basis, closing_price, value, percent_return)`. `read_assets_history_columns` (Task 2) order matches that SQL and is asserted by Task 2's schema-consistency test. `rebuild_asset_history()` (Task 6) used in Task 7. ✓

**Placeholder scan:** none — every code step carries concrete code and commands. ✓

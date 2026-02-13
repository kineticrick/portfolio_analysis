# Portfolio Analysis: Optimization & Improvement Analysis

*Analysis performed February 2026 using Claude Opus 4.6*

---

## Table of Contents

- [Part 1: Performance Optimizations](#part-1-performance-optimizations)
  - [Completed](#completed)
  - [Remaining: High Impact](#remaining-high-impact)
  - [Remaining: Medium Impact](#remaining-medium-impact)
- [Part 2: Visualization / UX Improvements](#part-2-visualization--ux-improvements)
  - [Architectural Issues](#architectural-issues)
  - [UX Gaps](#ux-gaps)
  - [Missing Features](#missing-features)
  - [Quick Wins](#quick-wins)
- [Part 3: Framework Assessment](#part-3-framework-assessment)
  - [Framework Comparison](#framework-comparison)
  - [Recommendation](#recommendation)
  - [Improvements Within Dash](#improvements-within-dash)

---

## Part 1: Performance Optimizations

### Completed

#### Batch INSERTs for History Handlers
**Commit:** `d72a7aa` | **Impact:** 5-20x faster history writes

Converted 5 history handlers from row-by-row `iterrows()` + `db.execute()` to `executemany()` batch inserts:
- `SectorHistoryHandler`
- `AssetTypeHistoryHandler`
- `AccountTypeHistoryHandler`
- `GeographyHistoryHandler`
- `AssetHypotheticalHistoryHandler`

These now match the pattern already used by `AssetHistoryHandler` and `PortfolioHistoryHandler`.

#### Database Indexes
**Commit:** `d72a7aa` | **Impact:** 2-5x faster queries

Added 11 secondary indexes across transaction and history tables to eliminate full table scans:

| Table | Index | Speeds Up |
|-------|-------|-----------|
| `trades` | `idx_trades_symbol` | `build_master_log()` symbol filtering |
| `trades` | `idx_trades_symbol_date` | Date-range + symbol queries |
| `dividends` | `idx_dividends_symbol` | Dividend lookups by symbol |
| `splits` | `idx_splits_symbol` | Split lookups by symbol |
| `entities` | `idx_entities_symbol` | `add_asset_info()` joins |
| `assets_history` | `idx_assets_history_symbol` | Symbol-only queries on history |
| `assets_hypothetical_history` | `idx_assets_hypo_history_symbol` | Hypothetical symbol lookups |
| `sectors_history` | `idx_sectors_history_sector` | Sector dimension filtering |
| `asset_types_history` | `idx_asset_types_history_type` | Asset type filtering |
| `account_types_history` | `idx_account_types_history_type` | Account type filtering |
| `geography_history` | `idx_geography_history_geo` | Geography filtering |

Indexes are created idempotently via `MysqlDB.create_index_safe()` (catches MySQL error 1061 for duplicate index names). Transaction table indexes are applied by `importer.py`; history table indexes are applied by `BaseHistoryHandler.gen_table()`.

---

### Remaining: High Impact

#### 1. `gen_hist_quantities()` is O(n^2)
**File:** `libraries/helpers.py:174` | **Estimated speedup:** 5-10x

**Problem:** Uses `iterrows()` to loop over every transaction event (slow — 10-100x slower than vectorized ops for large DataFrames). Inside the loop, `purchase_list.sort()` is called on every buy event, re-sorting the entire list each time — O(n^2) behavior overall.

```python
for _, event in asset_event_log_df.iterrows():  # slow iterrows
    # ... 85 lines of per-row processing ...
    purchase_list.append({...})
    purchase_list.sort(key=lambda x: x['Date'])  # re-sort on every buy!
```

**Fix options:**
- Replace `purchase_list.sort()` with `bisect.insort()` to maintain sorted order on insert (O(log n) per insert instead of O(n log n))
- Consider vectorizing the quantity/cost-basis tracking where possible, though the stateful nature of the logic (running totals, split handling) makes full vectorization complex
- At minimum, replace `iterrows()` with `itertuples()` for 3-5x speedup on the iteration itself

This function is on the critical path for all history generation.

#### 2. Redundant Computation in `DashboardHandler.__init__()`
**File:** `visualization/dash/DashboardHandler.py` | **Estimated speedup:** ~4x for dimension summaries

**Problem A — `gen_aggregated_historical_value()` called 4 times:**
Each dimension handler (Sector, AssetType, AccountType, Geography) calls `gen_aggregated_historical_value()` independently. Each call:
1. Re-fetches ALL historical data via `gen_assets_historical_value()`
2. Expands it with `add_asset_info()` (entity metadata merge)
3. Groups by one dimension

This means the full asset history is fetched and expanded 4 times, then grouped 4 different ways.

**Fix:** Compute all dimensions in a single pass:
```python
expanded_df = add_asset_info(assets_history_df)
for dimension in ['Sector', 'AssetType', 'AccountType', 'Geography']:
    results[dimension] = expanded_df.groupby(['Date', dimension])['PercentReturn'].mean()
```

**Problem B — Asset history loaded for ALL ever-owned assets:**
`AssetHistoryHandler()` on line 41 loads history for every asset ever owned (~200+), then line 53-54 filters down to current portfolio (~50 assets). The DB query should filter by symbol upfront.

**Fix:** Pass current portfolio symbols to `AssetHistoryHandler`:
```python
portfolio_symbols = self.current_portfolio_summary_df['Symbol'].tolist()
ah = AssetHistoryHandler(symbols=portfolio_symbols)
```

#### 3. `add_asset_info()` Loaded Multiple Times
**File:** `libraries/helpers.py:539` | **Estimated speedup:** Eliminates redundant DB calls

**Problem:** `add_asset_info()` fetches the entire entities table via `mysql_to_df()` on every call. It's called 3+ times during `DashboardHandler` initialization:
- In `expand_history_df()` (line 376)
- In `gen_historical_stats()` (line 495)
- In `get_portfolio_current_value()` (line 583)

Even with caching, each call still parses and merges the DataFrame.

**Fix:** Load entities once in `DashboardHandler.__init__()`, store as `self.entities_df`, and pass it to methods that need it.

---

### Remaining: Medium Impact

#### 4. `gen_historical_stats()` Per-Symbol Scalar Lookups
**File:** `visualization/dash/DashboardHandler.py:419-488` | **Estimated speedup:** 3-5x

**Problem:** For each symbol, performs 6 separate scalar lookups:
```python
for symbol in symbols:
    symbol_actuals_df = actuals_df.loc[actuals_df['Symbol'] == symbol]
    enter_price = symbol_actuals_df['ClosingPrice'].iloc[0]
    latest_actuals_price = symbol_actuals_df['ClosingPrice'].iloc[-1]
    max_actuals_price = symbol_actuals_df['ClosingPrice'].max()
    # ... etc
```

With 100+ assets, this is 300+ DataFrame operations.

**Fix:** Use vectorized groupby:
```python
price_stats = actuals_df.groupby('Symbol')['ClosingPrice'].agg(['first', 'last', 'max'])
```

#### 5. `build_master_log()` Concat-in-Loop
**File:** `libraries/helpers.py:62-78` | **Estimated speedup:** ~15-20%

**Problem:** Uses `pd.concat()` inside a loop (5 iterations for each event type) and `globals()` dictionary lookups for query/column names:
```python
for event in ASSET_EVENTS:
    query = globals()[f"master_log_{event}s_query"]   # dynamic lookup
    columns = globals()[f"master_log_{event}s_columns"]
    event_log_df = mysql_to_df(query, columns, dbcfg, cached=True)
    master_log_df = pd.concat([master_log_df, event_log_df])  # copies entire DF each time
```

**Fix:** Collect all DataFrames in a list, concat once at the end. Replace `globals()` lookups with a static mapping dict.

#### 6. Connection Pool Size
**File:** `libraries/db/mysqldb.py:14` | **Estimated speedup:** Reduces connection wait times

**Problem:** Pool size of 5 is conservative. If 7+ handlers try to acquire connections concurrently during initialization, some will block waiting for a connection.

**Fix:** Increase `pool_size` from 5 to 10.

#### 7. yfinance Cache Expiration Mismatch
**File:** `libraries/yfinance_helpers/yfinancelib.py:73, 166`

**Problem:** Historical prices (stable, past data) cache for 12 hours — too short, these rarely change. Current prices cache for 1 hour — too long for intraday relevance.

**Fix:**
- Historical prices: 24 hours (`expire=60*60*24`)
- Current prices: 15 minutes (`expire=60*15`)

#### 8. Calendar Days Instead of Business Days
**File:** `libraries/yfinance_helpers/yfinancelib.py:143`

**Problem:** `pd.date_range(start, end, freq='D')` creates entries for all calendar days, then forward-fills weekends/holidays. Creates ~30% unnecessary entries.

**Fix:** Use `pd.bdate_range(start, end)` for business days only.

#### 9. `_gen_summary_df()` Double GroupBy
**File:** `visualization/dash/DashboardHandler.py:551-562`

**Problem:** Groups by dimension twice (once for sums, once for means), then merges results:
```python
summary_df = portfolio_summary_df.groupby(dimension)[sum_cols].sum()
mean_df = portfolio_summary_df.groupby(dimension)[mean_cols].mean()
summary_df = summary_df.merge(mean_df, on=dimension)
```

**Fix:** Single groupby with `.agg()`:
```python
summary_df = portfolio_summary_df.groupby(dimension).agg({
    'Cost Basis': 'sum', 'Current Value': 'sum',
    'Total Dividend': 'sum', 'Dividend Yield': 'mean'
})
```

---

## Part 2: Visualization / UX Improvements

### Architectural Issues

#### 1. Global Mutable State in Callbacks
**Files:** `tabs/assets_tab.py:55`, `tabs/sectors_tab.py`, etc.

Tabs use `global assets_table_df, row_symbol_mapping` — mutating shared state in callbacks. This is fragile and will break with concurrent users.

**Fix:** Replace with `dcc.Store` for client-side state management.

#### 2. All Tabs Load at Startup
**Files:** `tabs/__init__.py`, `globals.py`

Every tab executes module-level code at import time, even tabs the user never visits. `DashboardHandler.__init__()` precomputes everything. No lazy loading — the user stares at a blank screen during initialization.

**Fix:** Use Dash Pages (lazy loading) or deferred tab initialization.

#### 3. Four Dimension Tabs are 90% Duplicate Code
**Files:** `tabs/sectors_tab.py`, `tabs/asset_types_tab.py`, `tabs/account_types_tab.py`, `tabs/geography_tab.py`

Nearly identical code maintained as separate files. A bug fix must be replicated 4 times.

**Fix:** Refactor into a single parameterized `DimensionTab` component/factory function.

### UX Gaps

#### 4. No Loading States
No `dcc.Loading` wrapper or skeleton screens. Users see nothing during initialization.

#### 5. Filter Logic is AND Instead of OR
**File:** `tabs/assets_tab.py:59-93`

Selecting a sector AND an asset type returns only assets matching BOTH, rather than the union. Counter-intuitive for exploratory filtering.

#### 6. No Data Freshness Indicator
No "last updated" timestamp, no refresh button. Data goes stale silently.

#### 7. Default Tab is Assets, Not Portfolio
**File:** `portfolio_dashboard.py:52`

`active_tab='assets-dash-tab'` — Portfolio overview should be the landing page.

#### 8. Chart Cluttering
No limit on selected assets for charting. Selecting 50+ assets makes the chart unreadable. Needs a warning or limit.

#### 9. Portfolio Tab Bug
**File:** `tabs/portfolio_tab.py:38`

Uses `port_hist_df['Value'][0]` instead of `port_hist_df['Value'].iloc[0]` — fragile if index isn't 0-based.

#### 10. Hardcoded Background Color
**File:** `tabs/portfolio_tab.py:109`

`paper_bgcolor = "lightblue"` — inconsistent with Bootstrap theme, not responsive to dark mode.

### Missing Features

- **No cross-filtering** between tabs (click sector -> filter assets)
- **No export** (CSV/Excel for tables, PNG for charts)
- **No benchmark comparison** (vs S&P 500, Russell 2000, etc.)
- **No secondary Y-axis** (absolute value + % change on same chart)
- **No date range slider** on charts (`rangeslider={'visible': True}`)
- **No conditional coloring** (green/red for positive/negative returns in tables)
- **No keyboard navigation** — DataTables require mouse for row selection (accessibility issue)

### Quick Wins

| Fix | Where | Effort |
|-----|-------|--------|
| Change default tab to Portfolio | `portfolio_dashboard.py:52` | 1 line |
| Add `dcc.Loading` wrapper | `portfolio_dashboard.py` around tabs | 2 lines |
| Format Y-axis as percentage | `fig.update_yaxes(tickformat=".1%")` | 1 line per chart |
| Use `iloc[0]` not `[0]` | `portfolio_tab.py:38` | 1 line |
| Replace `paper_bgcolor='lightblue'` | `portfolio_tab.py:109` | 1 line |
| Add `rangeslider={'visible': True}` | `portfolio_tab.py` chart config | 1 line |

---

## Part 3: Framework Assessment

### Framework Comparison

| Framework | Charts | Tables | Reactivity | Dev Speed | Polish | Ecosystem | **Overall** |
|-----------|--------|--------|------------|-----------|--------|-----------|-------------|
| **Dash** (current) | 9/10 | 7/10 | 8/10 | 6/10 | 7/10 | 9/10 | **8/10** |
| **Panel** (HoloViz) | 8/10 | 9/10 | 8/10 | 7/10 | 8/10 | 6/10 | **7.5/10** |
| **Shiny for Python** | 8/10 | 7/10 | 9/10 | 7/10 | 7/10 | 5/10 | **7/10** |
| **Streamlit** | 8/10 | 6/10 | 5/10 | 9/10 | 8/10 | 9/10 | **6.5/10** |
| **NiceGUI** | 7/10 | 7/10 | 6/10 | 8/10 | 9/10 | 4/10 | **5.5/10** |
| Voila | 7/10 | 6/10 | 4/10 | 5/10 | 4/10 | 5/10 | 3/10 |
| Gradio | 4/10 | 3/10 | 3/10 | 8/10 | 6/10 | 7/10 | 2/10 |
| Reflex | 6/10 | 4/10 | 7/10 | 4/10 | 8/10 | 4/10 | 2.5/10 |

### Recommendation

**Stay with Dash.** The migration cost doesn't justify marginal gains.

**Why:**
- The entire dashboard (7 tabs, complex table-to-chart interactivity, Plotly financial formatting) is already built on Dash
- Plotly charts are best-in-class for financial time series: `hover_data={'Value': ':$,.2f'}`, unified hover, line dash by category
- The pain points (verbose callbacks, DataTable quirks, global state) are all solvable within Dash
- Every alternative requires a full rewrite of 8+ files

**If starting from scratch**, Panel would be the strongest alternative:
- Tabulator table widget is the best data table in any Python framework (sorting, filtering, row selection, cell formatting, conditional formatting — all out of the box)
- hvPlot's `df.hvplot.line()` is more concise than Plotly Express
- Built-in dashboard templates (FastListTemplate, MaterialTemplate) give professional layouts with minimal effort

### Improvements Within Dash

These can be made incrementally without a framework migration:

1. **Replace `dash_table.DataTable` with `dash-ag-grid`** — Vastly better row selection, cell formatting (green/red returns), and filtering. Eliminates the `row_symbol_mapping` workaround entirely.

2. **Add `dash-mantine-components`** — More polished dropdowns, cards, and tabs than `dash-bootstrap-components`.

3. **Use Dash Pages** — Multi-page app pattern with lazy loading. Tabs only load when visited, improving startup time.

4. **Replace `global` state with `dcc.Store`** — Client-side state management, safe for concurrent users.

5. **Add `clientside_callback`** — Move simple filtering/sorting operations to JavaScript for instant response.

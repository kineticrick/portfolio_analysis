# Chart Rezeroing & Value-Weighted Aggregation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every history chart "rezero" to the start of the selected interval, and make dimension lines value-weighted, by storing aggregate value/cost-basis dollars instead of a pre-averaged percent.

**Architecture:** Replace the lossy `avg_percent_return` column in the four dimension history tables with `total_value`/`total_cost_basis`, add `cost_basis` to `portfolio_history`, and derive all displayed percentages at chart time. A new pure module `libraries/returns.py` holds the value-weighting and multiplicative-rebase math, unit-tested in isolation and shared by all three chart callbacks.

**Tech Stack:** Python, pandas, MySQL (mysql.connector), Dash/Plotly, unittest.

**Spec:** `docs/superpowers/specs/2026-06-15-chart-rezeroing-value-weighted-design.md`

**Test command convention:** `python -m unittest tests.libraries.<module> -v` (run from repo root with `venv` activated).

---

## File Structure

- **Create** `libraries/returns.py` — pure functions: value-weighted lifetime return; multiplicative window rebase. No DB/Dash imports.
- **Create** `tests/libraries/test_returns.py` — unit tests for the pure functions.
- **Modify** `libraries/helpers.py` — `gen_aggregated_historical_value` sums value/cost_basis instead of averaging returns.
- **Modify** `libraries/db/sql.py` — schema/insert/read defs for 4 dimension tables + `portfolio_history`.
- **Modify** `libraries/HistoryHandlers/{Sector,AssetType,AccountType,Geography}HistoryHandler.py` — set/get new columns.
- **Modify** `libraries/HistoryHandlers/PortfolioHistoryHandler.py` — aggregate + store `cost_basis`.
- **Modify** `visualization/dash/DashboardHandler.py` — `_gen_summary_df` derives the percent from new columns.
- **Modify** `visualization/dash/portfolio_dashboard/tabs/dimension_tab_factory.py` — derive `y` via `returns.py`.
- **Modify** `visualization/dash/portfolio_dashboard/tabs/assets_tab.py` — window rebase via `returns.py`.
- **Modify** `visualization/dash/portfolio_dashboard/tabs/portfolio_tab.py` — plot rebased / value-weighted line.
- **Modify** `visualization/dash/DemoDashboardHandler.py` — synthesize new columns.
- **Add tests to** `tests/libraries/test_helpers.py` — aggregation returns summed dollars.

---

## Task 1: Pure returns module

**Files:**
- Create: `libraries/returns.py`
- Test: `tests/libraries/test_returns.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/libraries/test_returns.py
import unittest
import pandas as pd
from libraries.returns import value_weighted_lifetime_return, rebase_to_window_start


class TestReturns(unittest.TestCase):
    def test_value_weighted_lifetime_return_biotech(self):
        # Real Biotech holdings on 2026-06-14: LLY + FATE
        total_value = pd.Series([27192.0 + 1809.0])
        total_cost_basis = pd.Series([13337.0 + 2602.0])
        result = value_weighted_lifetime_return(total_value, total_cost_basis)
        self.assertAlmostEqual(result.iloc[0], 81.95, places=1)

    def test_rebase_is_multiplicative_not_subtractive(self):
        # 3.25x -> 3.75x growth multiple over the window = 15.4%, not 50 "points"
        values = pd.Series([325.0, 375.0])
        result = rebase_to_window_start(values)
        self.assertAlmostEqual(result.iloc[0], 0.0, places=6)      # starts at 0%
        self.assertAlmostEqual(result.iloc[1], 15.3846, places=3)  # 375/325 - 1

    def test_rebase_first_point_is_zero(self):
        values = pd.Series([100.0, 110.0, 90.0])
        result = rebase_to_window_start(values)
        self.assertEqual(result.iloc[0], 0.0)
        self.assertAlmostEqual(result.iloc[2], -10.0, places=6)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.libraries.test_returns -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'libraries.returns'`.

- [ ] **Step 3: Write minimal implementation**

```python
# libraries/returns.py
"""Pure return-math helpers shared by the history chart callbacks.

No DB or Dash imports — keep this unit-testable in isolation.
"""
import pandas as pd


def value_weighted_lifetime_return(total_value: pd.Series,
                                   total_cost_basis: pd.Series) -> pd.Series:
    """Return-on-cost-basis for an aggregate, as a percent.

    Value-weighted because the inputs are summed dollars, not averaged ratios.
    """
    return (total_value - total_cost_basis) / total_cost_basis * 100


def rebase_to_window_start(values: pd.Series) -> pd.Series:
    """Multiplicative rebase of a value/price series to its first element.

    window_return(t) = values(t) / values(t0) - 1, expressed as a percent.
    The first element is therefore always 0%.
    """
    base = values.iloc[0]
    return (values / base - 1) * 100
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.libraries.test_returns -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add libraries/returns.py tests/libraries/test_returns.py
git commit -m "Add pure returns module (value-weighting + multiplicative rebase)"
```

---

## Task 2: Value-weighted aggregation in gen_aggregated_historical_value

**Files:**
- Modify: `libraries/helpers.py:487-528`
- Test: `tests/libraries/test_helpers.py` (add a test)

- [ ] **Step 1: Write the failing test**

Add to `tests/libraries/test_helpers.py` inside `class TestHelpers`:

```python
    def test_gen_aggregated_historical_value_is_value_weighted(self):
        # Two assets, same sector, very different sizes.
        # Big winner should dominate -> value-weighted, not a 50/50 average.
        import libraries.helpers as H
        H._aggregation_cache.clear()
        expanded = pd.DataFrame({
            'Date':       ['2024-01-01', '2024-01-01'],
            'Symbol':     ['BIG', 'SMALL'],
            'Value':      [29000.0, 1000.0],
            'CostBasis':  [16000.0, 2000.0],
            'PercentReturn': [81.25, -50.0],
            'Sector':     ['Biotech', 'Biotech'],
        })
        # Inject directly into the cache so we exercise the aggregation only.
        key = ((), 'daily', 'None')
        H._aggregation_cache[key] = expanded
        out = H.gen_aggregated_historical_value(dimension='Sector')
        row = out.iloc[0]
        self.assertEqual(set(['Date', 'Sector', 'total_value', 'total_cost_basis'])
                         .issubset(out.columns), True)
        self.assertAlmostEqual(row['total_value'], 30000.0)
        self.assertAlmostEqual(row['total_cost_basis'], 18000.0)
        H._aggregation_cache.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.test_helpers.TestHelpers.test_gen_aggregated_historical_value_is_value_weighted -v`
Expected: FAIL — output still has `AvgPercentReturn`, no `total_value`/`total_cost_basis`.

- [ ] **Step 3: Implement the aggregation change**

In `libraries/helpers.py`, replace the body from the groupby through the return (currently lines ~521-528):

```python
    # Aggregate by dimension and date by SUMMING dollars (value-weighted),
    # instead of averaging per-asset percent returns. Storing the dollar
    # primitives lets the charts derive lifetime returns AND rebase any window.
    aggregated_df = expanded_df.groupby(['Date', dimension]).agg(
        total_value=('Value', 'sum'),
        total_cost_basis=('CostBasis', 'sum'),
    ).reset_index()
    aggregated_df = aggregated_df.sort_values(by=[dimension, 'Date'],
                                              ascending=True)

    return aggregated_df
```

Also update the docstring return line (~499-502) to:

```python
    Returns: aggregated_df ->
    Date, [Dimension], total_value, total_cost_basis
    2016-02-17  Aerospace + Defense    12500.00   9000.00
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.test_helpers.TestHelpers.test_gen_aggregated_historical_value_is_value_weighted -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add libraries/helpers.py tests/libraries/test_helpers.py
git commit -m "Aggregate dimensions by summed value/cost_basis (value-weighted)"
```

---

## Task 3: Schema definitions in sql.py

**Files:**
- Modify: `libraries/db/sql.py` (portfolio_history ~184-201; sectors ~229-250; asset_types ~252-273; account_types ~275-296; geography ~298-319)

> No unit test (pure SQL string constants); verified end-to-end in Task 6.

- [ ] **Step 1: Update `portfolio_history` defs**

Replace lines ~185-201:

```python
create_portfolio_history_table_sql = \
    ("CREATE TABLE IF NOT EXISTS portfolio_history ("
    "date DATE NOT NULL, "
    "value DECIMAL(13, 2) NOT NULL, "
    "cost_basis DECIMAL(13, 2) NOT NULL, "
    "PRIMARY KEY (date))")

insert_ignore_portfolio_history_sql = \
    ("INSERT IGNORE INTO portfolio_history"
     "(date, value, cost_basis) VALUES ('{date}','{value}','{cost_basis}')")

insert_update_portfolio_history_sql = \
    ("INSERT INTO portfolio_history"
     "(date, value, cost_basis) VALUES ('{date}','{value}','{cost_basis}') "
     "ON DUPLICATE KEY UPDATE date='{date}', value='{value}', cost_basis='{cost_basis}'")

read_portfolio_history_query = "SELECT * FROM portfolio_history"
read_portfolio_history_columns = ['Date', 'Value', 'CostBasis']
```

- [ ] **Step 2: Update the four dimension tables**

For each of `sectors`/`asset_types`/`account_types`/`geography`, change the column `avg_percent_return DECIMAL(13, 2) NOT NULL` to two columns and update insert/read. Example for `sectors` (apply the same pattern to the other three, substituting the dimension column name `sector`→`asset_type`/`account_type`/`geography`):

```python
create_sectors_history_table_sql = \
    ("CREATE TABLE IF NOT EXISTS sectors_history ("
    "date DATE NOT NULL, "
    "sector VARCHAR(40) NOT NULL, "
    "total_value DECIMAL(15, 2) NOT NULL, "
    "total_cost_basis DECIMAL(15, 2) NOT NULL, "
    "PRIMARY KEY (date, sector))")

insert_ignore_sectors_history_sql = \
    ("INSERT IGNORE INTO sectors_history"
     "(date, sector, total_value, total_cost_basis) "
     "VALUES ('{date}','{sector}','{total_value}','{total_cost_basis}')")

insert_update_sectors_history_sql = \
    ("INSERT INTO sectors_history"
     "(date, sector, total_value, total_cost_basis) "
     "VALUES ('{date}','{sector}','{total_value}','{total_cost_basis}') "
     "ON DUPLICATE KEY UPDATE "
     "date='{date}', sector='{sector}', "
     "total_value='{total_value}', total_cost_basis='{total_cost_basis}'")

read_sectors_history_query = "SELECT * FROM sectors_history"
read_sectors_history_columns = ['Date', 'Sector', 'TotalValue', 'TotalCostBasis']
```

Apply identically to:
- `asset_types_history` (dim col `asset_type`, read cols `['Date', 'AssetType', 'TotalValue', 'TotalCostBasis']`)
- `account_types_history` (dim col `account_type`, read cols `['Date', 'AccountType', 'TotalValue', 'TotalCostBasis']`)
- `geography_history` (dim col `geography`, read cols `['Date', 'Geography', 'TotalValue', 'TotalCostBasis']`)

- [ ] **Step 3: Verify the module imports**

Run: `python -c "import libraries.db.sql"`
Expected: no error.

- [ ] **Step 4: Commit**

```bash
git add libraries/db/sql.py
git commit -m "Schema: store total_value/total_cost_basis in history tables"
```

---

## Task 4: Dimension handlers write/read new columns

**Files:**
- Modify: `libraries/HistoryHandlers/SectorHistoryHandler.py:36-72`
- Modify: `libraries/HistoryHandlers/AssetTypeHistoryHandler.py` (same shape)
- Modify: `libraries/HistoryHandlers/AccountTypeHistoryHandler.py` (same shape)
- Modify: `libraries/HistoryHandlers/GeographyHistoryHandler.py` (same shape)

- [ ] **Step 1: Update `SectorHistoryHandler.set_history`**

Replace the `with MysqlDB(...)` block body (lines ~42-57) with:

```python
        with MysqlDB(dbcfg) as db:
            if overwrite:
                sql = """REPLACE INTO sectors_history
                         (date, sector, total_value, total_cost_basis)
                         VALUES (%s, %s, %s, %s)"""
            else:
                sql = """INSERT IGNORE INTO sectors_history
                         (date, sector, total_value, total_cost_basis)
                         VALUES (%s, %s, %s, %s)"""

            values = [
                (row['Date'], row['Sector'],
                 float(row['total_value']), float(row['total_cost_basis']))
                for _, row in sectors_historical_data_df.iterrows()
            ]

            if values:
                db.cursor.executemany(sql, values)
                print(f"✓ Batch inserted {len(values)} sector history rows")
```

The `get_history` method needs no body change (it already reads via `read_sectors_history_columns`, now `['Date', 'Sector', 'TotalValue', 'TotalCostBasis']`). Update its docstring return to `Date, Sector, TotalValue, TotalCostBasis`.

- [ ] **Step 2: Apply the same change to the other three handlers**

For `AssetTypeHistoryHandler.py`, `AccountTypeHistoryHandler.py`, `GeographyHistoryHandler.py`: same edit, substituting the table name (`asset_types_history` etc.), the dimension column key in the row tuple (`row['AssetType']` / `row['AccountType']` / `row['Geography']`), and the dataframe variable name used in each file. The `gen_aggregated_historical_value` output columns are `total_value`/`total_cost_basis` for all four.

- [ ] **Step 3: Verify imports**

Run: `python -c "from libraries.HistoryHandlers import SectorHistoryHandler, AssetTypeHistoryHandler, AccountTypeHistoryHandler, GeographyHistoryHandler"`
Expected: no error.

- [ ] **Step 4: Commit**

```bash
git add libraries/HistoryHandlers/SectorHistoryHandler.py libraries/HistoryHandlers/AssetTypeHistoryHandler.py libraries/HistoryHandlers/AccountTypeHistoryHandler.py libraries/HistoryHandlers/GeographyHistoryHandler.py
git commit -m "Dimension handlers read/write total_value/total_cost_basis"
```

---

## Task 5: PortfolioHistoryHandler stores cost_basis

**Files:**
- Modify: `libraries/HistoryHandlers/PortfolioHistoryHandler.py:30-92`

- [ ] **Step 1: Aggregate cost basis alongside value**

In `set_history`, after building `daily_portfolio_value_df` from the groupby, change the aggregation to also sum cost basis. Replace lines ~51-92 logic so both columns are computed and inserted:

```python
        # Aggregate over dates to get total portfolio value AND cost basis per day
        daily_df = self.assets_history_df.groupby('Date').agg(
            Value=('Value', 'sum'),
            CostBasis=('CostBasis', 'sum'),
        ).reset_index()

        daily_df['Date'] = pd.to_datetime(daily_df['Date'])

        if start_date is not None:
            daily_df = daily_df[daily_df['Date'] >= start_date]

        with MysqlDB(dbcfg) as db:
            if overwrite:
                sql = """REPLACE INTO portfolio_history (date, value, cost_basis)
                         VALUES (%s, %s, %s)"""
            else:
                sql = """INSERT IGNORE INTO portfolio_history (date, value, cost_basis)
                         VALUES (%s, %s, %s)"""

            values = [
                (row['Date'].date(), float(row['Value']), float(row['CostBasis']))
                for _, row in daily_df.iterrows()
            ]

            if values:
                db.cursor.executemany(sql, values)
                print(f"✓ Batch inserted {len(values)} portfolio history rows")

        return self.get_history()
```

`get_history` needs no change (reads via `read_portfolio_history_columns`, now `['Date', 'Value', 'CostBasis']`).

- [ ] **Step 2: Verify import**

Run: `python -c "from libraries.HistoryHandlers import PortfolioHistoryHandler"`
Expected: no error.

- [ ] **Step 3: Commit**

```bash
git add libraries/HistoryHandlers/PortfolioHistoryHandler.py
git commit -m "PortfolioHistoryHandler stores aggregate cost_basis"
```

---

## Task 6: Migrate + re-derive history tables

**Files:** none (data migration script, run once)

- [ ] **Step 1: Drop the five tables so handlers recreate them with the new schema**

Run:

```bash
python - <<'EOF'
from libraries.db.mysqldb import MysqlDB
from libraries.db.dbcfg import dbcfg
with MysqlDB(dbcfg) as db:
    for t in ['portfolio_history','sectors_history','asset_types_history',
              'account_types_history','geography_history']:
        db.execute(f"DROP TABLE IF EXISTS {t}")
        print("dropped", t)
EOF
```

Expected: prints `dropped <table>` for all five.

- [ ] **Step 2: Re-derive by instantiating the handlers (they recreate + backfill)**

Run:

```bash
python - <<'EOF'
from libraries.HistoryHandlers import (PortfolioHistoryHandler, SectorHistoryHandler,
    AssetTypeHistoryHandler, AccountTypeHistoryHandler, GeographyHistoryHandler)
for cls in [PortfolioHistoryHandler, SectorHistoryHandler, AssetTypeHistoryHandler,
            AccountTypeHistoryHandler, GeographyHistoryHandler]:
    h = cls()
    print(cls.__name__, "rows:", len(h.history_df))
EOF
```

Expected: each prints a non-zero row count.

- [ ] **Step 3: Verify max dates and value-weighting**

Run:

```bash
python - <<'EOF'
from libraries.db.mysqldb import MysqlDB
from libraries.db.dbcfg import dbcfg
with MysqlDB(dbcfg) as db:
    for t in ['portfolio_history','sectors_history','asset_types_history',
              'account_types_history','geography_history']:
        db.execute(f"SELECT MAX(date), COUNT(*) FROM {t}")
        print(f"{t:24s}", db.fetchall()[0])
    # Biotech value-weighted lifetime return should be ~81.9% on latest date
    db.execute("""SELECT (total_value-total_cost_basis)/total_cost_basis*100
                  FROM sectors_history
                  WHERE sector='Biotech + Pharmaceuticals'
                    AND date=(SELECT MAX(date) FROM sectors_history)""")
    print("Biotech value-weighted lifetime %:", round(float(db.fetchall()[0][0]),1))
EOF
```

Expected: all tables max date `2026-06-14` (or the current latest trading day), and Biotech ≈ `81.9`.

- [ ] **Step 4: Commit (no code; record the migration ran)**

```bash
git commit --allow-empty -m "Re-derive history tables with value/cost_basis schema"
```

---

## Task 7: _gen_summary_df derives percent from new columns

**Files:**
- Modify: `visualization/dash/DashboardHandler.py:608-615`

> The dimension summary table merges the latest history row. With the new schema
> that row has `TotalValue`/`TotalCostBasis`; derive the displayed percent so the
> table's columns don't change shape.

- [ ] **Step 1: Replace the "avg daily return" merge block**

Replace lines ~608-615 with:

```python
        # Merge the latest history row, deriving the value-weighted return from
        # the stored dollars (history now stores TotalValue/TotalCostBasis).
        latest_history_date = history_df['Date'].max()
        latest_history_df = history_df.loc[
            history_df['Date'] == latest_history_date].copy()
        latest_history_df = latest_history_df.reset_index(drop=True)
        latest_history_df['AvgPercentReturn'] = (
            (latest_history_df['TotalValue'] - latest_history_df['TotalCostBasis'])
            / latest_history_df['TotalCostBasis'] * 100)
        latest_history_df = latest_history_df.drop(
            columns=['Date', 'TotalValue', 'TotalCostBasis'])
        summary_df = summary_df.merge(latest_history_df, on=dimension, how='left')
```

- [ ] **Step 2: Verify import**

Run: `python -c "import visualization.dash.DashboardHandler"`
Expected: no error.

- [ ] **Step 3: Commit**

```bash
git add visualization/dash/DashboardHandler.py
git commit -m "Derive dimension summary percent from stored dollars"
```

---

## Task 8: Dimension chart callback derives y from dollars

**Files:**
- Modify: `visualization/dash/portfolio_dashboard/tabs/dimension_tab_factory.py:1-79`

- [ ] **Step 1: Import the returns helpers**

At the top of the file (after existing imports), add:

```python
from libraries.returns import value_weighted_lifetime_return, rebase_to_window_start
```

- [ ] **Step 2: Replace the interval/plot block (lines ~61-77)**

```python
        # Derive the displayed series from the stored dollars.
        if interval == "Lifetime":
            history_df = history_df.copy()
            history_df['y'] = value_weighted_lifetime_return(
                history_df['TotalValue'], history_df['TotalCostBasis'])
        else:
            interval_days = {k: v for (k, v) in DASH_HANDLER.performance_milestones}
            days = interval_days[interval]
            offset = DateOffset(days=days)
            start_date = (pd.to_datetime('today') - offset).date()
            history_df = history_df[history_df['Date'] >= start_date].copy()
            history_df = history_df.sort_values(['Date'])
            # Rebase each dimension to ITS OWN value at the window start.
            history_df['y'] = history_df.groupby(column_name)['TotalValue'].transform(
                rebase_to_window_start)

        fig = px.line(
            history_df,
            x=history_df['Date'],
            y=history_df['y'],
            hover_data={'y': ':.2f%'},
            color=history_df[column_name],
        )
        fig.update_layout(height=800)
        fig.update_yaxes(ticksuffix="%")
```

- [ ] **Step 3: Verify import**

Run: `python -c "import visualization.dash.portfolio_dashboard.tabs.dimension_tab_factory"`
Expected: no error (note: importing may require DASH_HANDLER env; if it errors on DB, that's covered by the smoke test in Task 12 instead — confirm at least no `ImportError`/`NameError` from the edit).

- [ ] **Step 4: Commit**

```bash
git add visualization/dash/portfolio_dashboard/tabs/dimension_tab_factory.py
git commit -m "Dimension charts: value-weighted lifetime + window rebase"
```

---

## Task 9: Asset chart window rebase

**Files:**
- Modify: `visualization/dash/portfolio_dashboard/tabs/assets_tab.py:79-114`

- [ ] **Step 1: Import the rebase helper**

Add near the top of `assets_tab.py`:

```python
from libraries.returns import rebase_to_window_start
```

- [ ] **Step 2: Rebase ClosingPrice per asset within the window**

Replace the interval-filter + plot section (lines ~93-114) with:

```python
        # Filter by interval, then rebase each asset's price to the window start
        # so the line starts at 0% for the selected period.
        if interval != "Lifetime":
            interval_days = {k: v for (k, v) in DASH_HANDLER.performance_milestones}
            days = interval_days.get(interval, 365)
            offset = DateOffset(days=days)
            start_date = (pd.to_datetime('today') - offset).date()
            expanded_df = expanded_df[expanded_df['Date'] >= start_date].copy()
            expanded_df = expanded_df.sort_values(['Symbol', 'Date'])
            expanded_df['ClosingPrice % Change'] = expanded_df.groupby('Symbol')[
                'ClosingPrice'].transform(rebase_to_window_start)

        if expanded_df.empty:
            return go.Figure().update_layout(
                title="No data available. Select assets from the table above.")

        fig = px.line(
            expanded_df,
            x=expanded_df['Date'],
            y=expanded_df['ClosingPrice % Change'],
            hover_data={'Value': ':$,.2f', 'ClosingPrice % Change': ':.2f%'},
            color=expanded_df['Symbol'],
            line_dash=expanded_df['Sector'],
        )
        fig.update_layout(height=800)
        fig.update_yaxes(ticksuffix="%")
```

(For `Lifetime`, the precomputed inception-based `ClosingPrice % Change` from `expand_history_df` is used unchanged.)

- [ ] **Step 3: Verify import**

Run: `python -c "import visualization.dash.portfolio_dashboard.tabs.assets_tab"`
Expected: no `ImportError`/`NameError` from the edit.

- [ ] **Step 4: Commit**

```bash
git add visualization/dash/portfolio_dashboard/tabs/assets_tab.py
git commit -m "Asset chart: rebase price to window start per asset"
```

---

## Task 10: Portfolio chart plots rebased / value-weighted line

**Files:**
- Modify: `visualization/dash/portfolio_dashboard/tabs/portfolio_tab.py:14-52`

- [ ] **Step 1: Import the helpers**

Add near the top of `portfolio_tab.py`:

```python
from libraries.returns import value_weighted_lifetime_return, rebase_to_window_start
```

- [ ] **Step 2: Compute y by interval and plot percent**

Replace the body from the slice through the `px.line` (lines ~31-48) with:

```python
        port_hist_df = port_hist_df[port_hist_df.index >= date].copy()

        if port_hist_df.empty:
            return go.Figure().update_layout(title="No data available for selected interval")

        port_hist_df['Value'] = port_hist_df['Value'].astype(float)
        port_hist_df['CostBasis'] = port_hist_df['CostBasis'].astype(float)

        if interval == "Lifetime":
            # Value-weighted return on invested capital
            port_hist_df['y'] = value_weighted_lifetime_return(
                port_hist_df['Value'], port_hist_df['CostBasis'])
        else:
            port_hist_df['y'] = rebase_to_window_start(port_hist_df['Value'])

        fig = px.line(
            port_hist_df,
            x=port_hist_df.index,
            y=port_hist_df['y'],
            hover_data={'Value': ':$,.2f', 'y': ':.2f%'},
            markers=True,
        )
        fig.update_yaxes(ticksuffix="%")
```

(Keep the existing `fig.update_layout(...)` rangeslider line that follows.)

- [ ] **Step 3: Verify import**

Run: `python -c "import visualization.dash.portfolio_dashboard.tabs.portfolio_tab"`
Expected: no `ImportError`/`NameError` from the edit.

- [ ] **Step 4: Commit**

```bash
git add visualization/dash/portfolio_dashboard/tabs/portfolio_tab.py
git commit -m "Portfolio chart: plot rebased % / value-weighted lifetime line"
```

---

## Task 11: Demo handler synthesizes new columns

**Files:**
- Modify: `visualization/dash/DemoDashboardHandler.py:321-330` (portfolio history) and `:462-468` (dimension history)

> The demo `assets_history_df` already carries `CostBasis` (lines 235/255), so the
> expanded df does too — no demo data-generation change needed. Two construction
> sites need the cost-basis column added.

- [ ] **Step 1: Add CostBasis to the demo portfolio history**

Replace lines ~321-330:

```python
        port_hist = (
            self.portfolio_assets_history_df
            .groupby('Date')
            .agg(Value=('Value', 'sum'), CostBasis=('CostBasis', 'sum'))
            .reset_index()
        )
        port_hist['Date'] = pd.to_datetime(port_hist['Date'])
        self.portfolio_history_df = port_hist.set_index('Date')
        # Append today's value + latest cost basis (mirrors DashboardHandler pattern)
        today_cost_basis = float(port_hist['CostBasis'].iloc[-1])
        self.portfolio_history_df.loc[pd.to_datetime('today')] = \
            [self.current_portfolio_value, today_cost_basis]
```

- [ ] **Step 2: Build total_value/total_cost_basis for dimension history**

Replace the `dim_history` construction (lines ~462-468) with:

```python
        # Sum dollars per (Date, dimension-value) — mirrors the real handlers'
        # total_value/total_cost_basis columns.
        dim_history = (
            expanded
            .groupby(['Date', dimension])
            .agg(TotalValue=('Value', 'sum'),
                 TotalCostBasis=('CostBasis', 'sum'))
            .reset_index()
        )
```

Then keep the existing `dim_history['Date'] = pd.to_datetime(dim_history['Date']).dt.date`
and `sort_values` lines that follow (they still apply).

- [ ] **Step 3: Verify demo import + columns**

Run:

```bash
PORTFOLIO_DEMO_MODE=1 python -c "
from visualization.dash.DemoDashboardHandler import DemoDashboardHandler
h = DemoDashboardHandler()
print('portfolio cols:', list(h.portfolio_history_df.columns))
print('sectors cols:', list(h.sectors_history_df.columns))
"
```

Expected: portfolio cols include `Value` and `CostBasis`; sectors cols include `TotalValue`, `TotalCostBasis`.

- [ ] **Step 4: Commit**

```bash
git add visualization/dash/DemoDashboardHandler.py
git commit -m "Demo handler synthesizes total_value/total_cost_basis + portfolio cost basis"
```

---

## Task 12: Full-suite + dashboard smoke verification

**Files:** none

- [ ] **Step 1: Run the unit suite**

Run: `python -m unittest tests.libraries.test_returns tests.libraries.test_helpers tests.libraries.test_base_history_handler -v`
Expected: all PASS (the pre-existing pandas `'1M'` test was fixed earlier on `main`; if running off an older base, ensure that fix is present).

- [ ] **Step 2: Launch the dashboard on a free port**

Run (background):

```bash
python - > /tmp/dash_verify.log 2>&1 <<'EOF' &
import importlib.util, os
path = os.path.join('visualization','dash','portfolio_dashboard','portfolio_dashboard.py')
spec = importlib.util.spec_from_file_location('portfolio_dashboard', path)
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
mod.app.run(port=8053, debug=False)
EOF
```

Wait for `Dash is running` in `/tmp/dash_verify.log`.

- [ ] **Step 3: Drive a dimension chart at a window and confirm it rezeroes**

```bash
curl -s -X POST http://127.0.0.1:8053/_dash-update-component \
  -H "Content-Type: application/json" \
  -d '{"output":"..sectors-table.columnDefs...sectors-table.rowData...sectors-history-graph.figure..","outputs":[{"id":"sectors-table","property":"columnDefs"},{"id":"sectors-table","property":"rowData"},{"id":"sectors-history-graph","property":"figure"}],"inputs":[{"id":"tabs","property":"value","value":"sectors-dash-tab"},{"id":"sectors-table","property":"selectedRows","value":null},{"id":"sectors-interval-dropdown","property":"value","value":"3m"}],"changedPropIds":["tabs.value"]}' \
  | python -c "import json,sys; f=json.load(sys.stdin)['response']['sectors-history-graph']['figure']; [print(t['name'], 'first y=', (t.get('y') or [None])[0]) for t in f['data'][:5]]"
```

Expected: each trace's first `y` value is `0.0` (rezeroed to the window start).

- [ ] **Step 4: Confirm Lifetime matches the value-weighted summary**

```bash
curl -s -X POST http://127.0.0.1:8053/_dash-update-component \
  -H "Content-Type: application/json" \
  -d '{"output":"..sectors-table.columnDefs...sectors-table.rowData...sectors-history-graph.figure..","outputs":[{"id":"sectors-table","property":"columnDefs"},{"id":"sectors-table","property":"rowData"},{"id":"sectors-history-graph","property":"figure"}],"inputs":[{"id":"tabs","property":"value","value":"sectors-dash-tab"},{"id":"sectors-table","property":"selectedRows","value":null},{"id":"sectors-interval-dropdown","property":"value","value":"Lifetime"}],"changedPropIds":["tabs.value"]}' \
  | python -c "import json,sys; f=json.load(sys.stdin)['response']['sectors-history-graph']['figure']; print([(t['name'],(t.get('y') or [None])[-1]) for t in f['data']])"
```

Expected: the Biotech trace's last `y` ≈ `81.9`.

- [ ] **Step 5: Stop the server**

```bash
P=$(ss -ltnp 2>/dev/null | grep ':8053' | grep -oP 'pid=\K[0-9]+' | head -1); [ -n "$P" ] && kill "$P"
```

- [ ] **Step 6: Final commit (empty, marks verification complete)**

```bash
git commit --allow-empty -m "Verify rezeroing + value-weighting end-to-end"
```

---

## Self-Review

- **Spec coverage:** data model (Tasks 3,5), aggregation (Task 2), derived series + formulas (Task 1, consumed in 8/9/10), per-chart changes dimension/asset/portfolio (Tasks 8/9/10), demo (Task 11), `_gen_summary_df` consumer (Task 7), migration/re-derivation (Task 6), testing (Tasks 1,2,12). D1 (replace) realized in Tasks 3-6; D2 (seam) reflected by Lifetime=cost-basis vs window=value-ratio in Tasks 8/10; D3 (scope) = Tasks 8/9/10 + portfolio cost_basis in Tasks 3/5/10.
- **Names consistent:** stored DB columns `total_value`/`total_cost_basis`; read-column labels `TotalValue`/`TotalCostBasis`; helpers `value_weighted_lifetime_return`, `rebase_to_window_start` used identically across Tasks 8/9/10.
- **Out of scope:** Approach C / TWR explicitly deferred (spec).

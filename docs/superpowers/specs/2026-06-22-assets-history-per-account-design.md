# Per-account `assets_history` (fix multi-account row loss)

**Date:** 2026-06-22
**Status:** Approved (design)

## Problem

`assets_history` has `PRIMARY KEY (date, symbol)` and `AssetHistoryHandler.set_history`
writes with `INSERT IGNORE`. But `gen_assets_historical_value` emits one row per
`[Symbol, AccountType]`, so a symbol held in **two** account types (e.g. QQQ, VGT, VOO)
produces two rows with the same `(date, symbol)` and `INSERT IGNORE` silently keeps only
one — dropping the other account's quantity/value.

Impact is broader than the per-asset view: `PortfolioHistoryHandler` builds the **total**
portfolio value by `groupby('Date').sum()` over `assets_history`, so the dropped row also
**understates the Portfolio tab and portfolio history** for any period a multi-account
symbol was held. `assets_hypothetical_history` derives from `assets_history` and is
likewise affected. Dimension tables (Sector/AssetType/AccountType/Geography) are **not**
affected — they recompute from transactions via `gen_aggregated_historical_value`.

## Decision

Store `assets_history` **per account** — one row per `(date, symbol, account_type)` —
rather than collapsing to per-symbol. Rationale: the Assets-tab table is already
per-account (the `summary` table's PK includes `account_type`), but the Assets-tab chart
is per-symbol and currently shows the *understated* total. A faithful per-account history
table makes the data model consistent and lets a future Assets-tab feature show a symbol's
true history in each account as a fast, direct read (consistent with the cache-for-speed
architecture). `assets_history` is a derived cache; transactions remain the source of
truth.

**Scope: foundation only.** This change fixes the bug and stores per-account data, plus
rebuilds the affected tables. It does **not** build the Assets-tab UI to display
per-account lines — that is a separate follow-up.

## Key subtlety: account-label leak

`gen_assets_historical_value`'s `AccountType` column leaks `'Agnostic'` onto split/
acquisition dates: `gen_hist_quantities` stamps the per-*event* `AccountType`, and a split
event (tagged `'Agnostic'`) ffills forward through a single account's series. With the new
`(date, symbol, account_type)` primary key, two accounts both holding a symbol across a
split would each emit an `'Agnostic'`-labeled row for the same `(date, symbol)` — a fresh
primary-key collision, re-introducing the drop.

The true account is known only inside `gen_hist_quantities_mult`'s per-series loop
(`account_type` loop variable; `ACCOUNT_TYPES = ['Discretionary', 'Retirement']`). So the
label must be cleaned there.

## Architecture

### 1. Clean account labels — `libraries/helpers.py` (`gen_hist_quantities_mult`)

After computing each `[Symbol, account_type]` series via `gen_hist_quantities`, stamp the
series' true account on every row:

```python
symbol_quantities_df['AccountType'] = account_type
```

Now every value row carries `Discretionary`/`Retirement` (never `Agnostic`), making
`(date, symbol, account_type)` collision-free.

**Consequence (verify, do not regress):** the **AccountType dimension** history
(`gen_aggregated_historical_value(dimension='AccountType')`) currently groups on the leaked
label and can show a spurious `Agnostic` bucket / misattribute split-date value. Stamping
corrects it. Only the label changes — quantity/cost/value are identical — so portfolio
totals and the Sector-based `Disc + Ret == full` account-filter invariant are unaffected.

### 2. Schema — `libraries/db/sql.py`

- `create_assets_history_table_sql`: add `account_type VARCHAR(100) NOT NULL`; change
  `PRIMARY KEY (date, symbol)` → `PRIMARY KEY (date, symbol, account_type)`.
- Update the `assets_history` insert SQL(s) and `read_assets_history_columns` to include
  `account_type` / `AccountType`.
- Update any `assets_history` entry in `history_table_indexes` to match.

### 3. `AssetHistoryHandler` — `libraries/HistoryHandlers/AssetHistoryHandler.py`

- `set_history`: insert per-`(date, symbol, account_type)` rows directly from the
  (now clean-labeled) `gen_assets_historical_value` output — no collapse, no dropped rows.
  Include `AccountType` in the inserted tuple for both the append (`INSERT IGNORE`, now
  collision-free) and overwrite (`REPLACE`) paths.
- `get_history`: returns the new `AccountType` column; `read_assets_history_columns`
  includes `AccountType`. `history_df` is now per-account.

### 4. Per-symbol aggregation for existing readers — `libraries/helpers.py`

Add a pure helper:

```python
def aggregate_assets_history_by_symbol(df) -> pd.DataFrame:
    """Collapse per-(date,symbol,account) rows to per-(date,symbol) totals:
    sum Quantity/CostBasis/Value, take ClosingPrice first (identical per ticker/date),
    recompute PercentReturn = (Value - CostBasis)/CostBasis*100 (guard zero cost)."""
```

Wire it in where one row per symbol is assumed:

- `DashboardHandler.__init__`: expose **both**
  - `self.assets_history_by_account_df = ah.history_df` (per-account, faithful — for the
    future Assets-tab feature), and
  - `self.assets_history_df = aggregate_assets_history_by_symbol(ah.history_df)`
    (per-symbol totals — what all current consumers use).

  Aggregating once here keeps the per-asset chart, rankings, milestones, and stats correct
  and unchanged in appearance.
- `AssetHypotheticalHistoryHandler`: ensure its actuals operate on the per-symbol view
  (aggregate if it fetched per-account rows itself).
- `PortfolioHistoryHandler`: **no change** — `groupby('Date').sum()` is already correct
  over per-account rows (sum per date = total).

### 5. One-time rebuild — `generators/rebuild_asset_history.py` (new)

Because the schema changes, the script:
1. `DROP TABLE IF EXISTS assets_history`; recreate with the new schema
   (`create_assets_history_table_sql`).
2. Regenerate `assets_history` per-account, full history (overwrite).
3. `TRUNCATE` + regenerate `portfolio_history` and `assets_hypothetical_history`, in
   dependency order (both derive from the corrected `assets_history`).
4. Evict the history cache (`mysql_cache_evict(MYSQL_CACHE_HISTORY_TAG)`).

All three tables are fully regenerable from transactions + cached prices. Documented as a
one-time maintenance step in the README (not wired into dashboard startup).

## Data contracts (after change)

- `assets_history` row: `Date, Symbol, AccountType, Quantity, CostBasis, ClosingPrice,
  Value, PercentReturn`; key `(date, symbol, account_type)`.
- `DashboardHandler.assets_history_df`: per-symbol totals (existing columns, no
  `AccountType`) — unchanged contract for existing consumers.
- `DashboardHandler.assets_history_by_account_df`: per-account rows incl. `AccountType`
  (new; consumed by the future Assets-tab per-account view).

## Testing

- **Account-label cleaning:** `gen_assets_historical_value` output `AccountType` ⊆
  `{Discretionary, Retirement}` (no `Agnostic`); a multi-account symbol across a split has
  distinct, correctly-labeled rows.
- **Per-account round-trip (real DB):** after the fix, a known multi-account symbol (e.g.
  QQQ) has two rows per date in `assets_history`, and `(date, symbol, account_type)` is
  unique (no dup keys).
- **`aggregate_assets_history_by_symbol`:** a multi-account symbol on a date collapses to
  one row with summed quantity/value/cost and a return recomputed from the summed totals;
  single-account symbol unchanged; price preserved; zero-cost guarded.
- **Per-symbol totals match source:** the aggregated quantity for a multi-account symbol
  equals its transaction-derived total (catches any over/under-count).
- **Regressions:** portfolio totals unchanged in value; the Sector `Disc + Ret == full`
  invariant still passes; AccountType dimension no longer contains `Agnostic`; full suite
  green.

## Out of scope

- Assets-tab UI to display per-account lines (selection/color by `(Symbol, AccountType)`,
  any toggle) — separate follow-up, now enabled by the stored per-account data.
- Dimension history tables other than the AccountType-label cleanup consequence above.

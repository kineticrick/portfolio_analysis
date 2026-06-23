# Chat: Filterable Dimension Breakdowns

**Date:** 2026-06-22
**Status:** Approved (design)

## Problem

The chat intelligence layer cannot answer questions like *"Show me the top 5 sectors
from my discretionary account over the last 6 months."* The `get_dimension_breakdown`
tool aggregates across the **entire** portfolio with no way to filter, so the model
apologizes:

> "the get_dimension_breakdown tool doesn't support filtering by account type, so the
> sector returns above reflect your entire portfolio."

We want filtered dimension breakdowns (and the matching dimension line chart) to work
naturally — e.g. a sector breakdown restricted to the Discretionary account, or an
asset-type breakdown restricted to US holdings.

## Why the cached data can't answer this

- The dimension history tables (`sectors_history`, etc.) are **pre-aggregated across the
  whole portfolio**. There is no account-type granularity stored.
- The `assets_history` table has `PRIMARY KEY (date, symbol)` and is written with
  `INSERT IGNORE`. A symbol held in two account types (e.g. QQQ, VGT, VOO) collapses to a
  single row, so even the per-asset stored data cannot be split by account.

Therefore account-type filtering must **recompute from transactions**, not read a cached
table. The good news: the compute layer already supports per-account math —
`gen_hist_quantities_mult` separates by `[Symbol, AccountType]` and applies `Agnostic`
(split/acquisition) events per account.

## Two kinds of filter, applied where each is correct

| Filter key | Nature | Where applied |
|---|---|---|
| `account_type` | transaction-level | `build_master_log` — restrict events to `{account_type, 'Agnostic'}` |
| `sector`, `asset_type`, `geography` | entity attribute (static per symbol) | symbol-subset — restrict the `symbols` passed into the aggregation |

**Why `account_type` must be filtered at `build_master_log`, not by row:** within a single
account's quantity series, split/acquisition rows are labeled `'Agnostic'` (and that label
ffills forward). Filtering output rows on `AccountType == 'Discretionary'` would wrongly
drop those rows. Filtering the **input** events to `{account_type, 'Agnostic'}` instead
yields a clean computation where every resulting row belongs to that account, regardless
of its (possibly `Agnostic`) label. `gen_hist_quantities_mult` then naturally includes
only `[Symbol, account_type]` pairs that exist in the filtered log, so a symbol held only
in the *other* account is correctly excluded.

## Architecture

### 1. Compute layer (`libraries/helpers.py`)

Add an optional `account_type: str = None` parameter, threaded straight down:

- `build_master_log(symbols=[], account_type=None)` — when set, after building the log,
  keep only rows where `AccountType in {account_type, 'Agnostic'}`.
- `gen_assets_historical_value(..., account_type=None)` — pass through to
  `build_master_log`.
- `gen_aggregated_historical_value(dimension, symbols=[], ..., account_type=None)` — pass
  through; add `account_type` to the `_aggregation_cache` key. (The symbol subset already
  distinguishes entity filters.)

Entity filters need no new compute-layer parameter — they are expressed purely as the
`symbols` subset passed in.

### 2. Handler seam (`visualization/dash/DashboardHandler.py`)

New method:

```python
def get_filtered_dimension_breakdown(self, dimension, account_type=None,
                                     symbols=None, start_date=None) -> pd.DataFrame:
    """Per-member value + value-weighted return for `dimension`, optionally
    restricted to one account_type and/or a symbol subset, over [start_date, today]."""
```

It calls `gen_aggregated_historical_value(dimension, symbols=symbols or [],
start_date=start_date, account_type=account_type)` and derives, per dimension member,
the value-weighted return — matching the existing unfiltered tool exactly:

- **Lifetime** (`start_date=None`): cost-based, `(total_value - total_cost) / total_cost`
  (same definition as the `VW Return` column the unfiltered Lifetime path reads from the
  summary dataframe).
- **Window** (`start_date` set): rebased, `total_value(end) / total_value(start) - 1`
  (same as the unfiltered window path).

plus each member's total current value.

This is the single reusable seam shared by the text breakdown and the line chart.

### 3. Chat tools (`libraries/chat/tools.py`)

- `get_dimension_breakdown(handler, dimension, interval="Lifetime", filters=None)`:
  - **No filters** → existing fast cached path (summary / history dataframes). Unchanged.
  - **Filters present** → split `filters` into `account_type` vs entity filters
    (reuse `_filter_symbols` to resolve entity filters to a symbol subset), call
    `handler.get_filtered_dimension_breakdown(...)`, format per-member value + VW return.
- `show_history_line(handler, target_type, targets, interval, filters=None)`: for
  `target_type == "dimension"`, when `filters` present, build the line series from the
  same handler method instead of the cached dimension history.
- `TOOL_SCHEMAS`: advertise `filters` (object with `sector` / `asset_type` /
  `account_type` / `geography` string properties) on `get_dimension_breakdown` and
  `show_history_line`.
- Unknown filter keys continue to raise the existing descriptive `ValueError` via
  `_filter_symbols`.

### 4. Prompt (`libraries/chat/config.py`)

Remove / update any `SYSTEM_PROMPT` wording implying breakdowns can't be filtered, so the
model uses the new `filters` argument instead of apologizing.

## Data flow (filtered query)

```
user: "top sectors in my discretionary account, last 6m"
  -> get_dimension_breakdown(dimension="Sector", interval="6m",
                             filters={"account_type": "Discretionary"})
     -> split filters: account_type="Discretionary", entity filters none
     -> handler.get_filtered_dimension_breakdown("Sector",
                                                 account_type="Discretionary",
                                                 start_date=<6m ago>)
        -> gen_aggregated_historical_value("Sector", symbols=[],
                                           account_type="Discretionary",
                                           start_date=<6m ago>)   [cached]
           -> gen_assets_historical_value(account_type="Discretionary", ...)
              -> build_master_log(account_type="Discretionary")  [events filtered]
     -> per-sector value + VW return -> text
```

## Performance

On-demand + cached (per approval). Historical prices are already disk-cached from startup,
so a filtered recompute is mainly the master-log + quantities pass for the relevant
symbols — fast after the first call. The `_aggregation_cache` (extended with
`account_type`) makes repeat filtered queries instant. No added startup cost.

## Error handling

- Unknown filter key → descriptive `ValueError` from `_filter_symbols` (already implemented),
  surfaced to the model via `dispatch`.
- Empty result (no holdings match the filter / account) → clear "no holdings match …"
  message, no chart.
- Invalid interval → existing interval validation messaging.

## Testing

- **Correctness invariant (key test, real DB):** for every dimension member and date,
  `Discretionary total + Retirement total == unfiltered total`. This proves the
  `build_master_log` account filter neither drops nor double-counts (catches the
  `Agnostic`-leak failure mode).
- `build_master_log(account_type=...)` keeps only `{account_type, 'Agnostic'}` events.
- Entity-subset filtering: a `geography`/`sector` filter restricts members to the expected
  symbols.
- Tool routing: `get_dimension_breakdown` / `show_history_line` with `filters` call the
  handler's filtered method; without `filters` use the cached path (fake handler).
- `TOOL_SCHEMAS` advertises `filters` on both tools.

## Out of scope

- **`assets_history` multi-account `INSERT IGNORE` bug** — pre-existing; the stored
  per-asset history drops one row for multi-account symbols. It does not affect this
  feature (we recompute) or dimension totals (those recompute correctly). The user has
  chosen to fix it as a **separate follow-up after this work**.
- No new precomputed per-account history tables (rejected for startup/storage cost).

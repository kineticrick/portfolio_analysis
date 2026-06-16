# Chart Rezeroing & Value-Weighted Aggregation — Design

**Date:** 2026-06-15
**Status:** Approved (design) — pending implementation plan
**Approach:** A (value-level aggregation), scope: all three chart families + portfolio cost basis

## Problem

When a non-Lifetime interval (1w, 1m, 3m, …) is selected, the history charts do not
"rezero" to the start of the selected window. They slice the series and plot the
**absolute, since-inception** measure, so a line that was at +225% three months ago and
is at +275% today is drawn 225 → 275 instead of starting at 0% and showing the window's
actual move.

Two distinct defects underlie this:

1. **Rebasing (all charts):** the displayed percentage is computed against an inception
   baseline, then the window is sliced — instead of being rebased to the window's first
   point.
2. **Lossy aggregation (dimension charts only):** dimension lines store the *average of
   member assets' lifetime percent returns*, which (a) is not value-weighted and (b)
   discards the dollar values needed to rebase a window at all.

## Core concepts (rationale)

**Multiplicative rebase.** Percent return is a ratio against a fixed anchor (cost basis),
so you cannot subtract two returns to get a window return. Convert to a growth multiple
`M(t) = 1 + R(t)` and divide: `window_return = M(t₁)/M(t₀) − 1`. Equivalently, on the
underlying value series, `value(t₁)/value(t₀) − 1`. Example: +225% → +275% is
`3.75/3.25 − 1 = 15.4%`, not `50/225 = 22%` and not "+50 points".

**Value-weighting.** A dimension combines several holdings. Averaging their percentages
gives a tiny and a huge position equal weight. The honest aggregate sums the dollars
first: `sector_return = (Σ value − Σ cost_basis) / Σ cost_basis`. Real example
(Biotech, 2026-06-14): LLY (cb $13,337 → $27,192, +103.9%) and FATE (cb $2,602 → $1,809,
−30.5%) give an unweighted average of **36.7%** but a value-weighted **81.9%** — the
value-weighted figure is what the actual biotech dollars did.

The two fixes share a root: storing dollars (value + cost basis) instead of a pre-reduced
percentage makes both correct rebasing and value-weighting fall out directly.

## Current behavior (precise)

| Chart | Code | What it plots | Defect |
|---|---|---|---|
| Dimension (sectors, asset_types, account_types, geography) | `dimension_tab_factory.py:62-75` | `AvgPercentReturn`, sliced | Not rebased **and** lossy/unweighted aggregation |
| Per-asset | `assets_tab.py:94-108` | `ClosingPrice % Change` (computed since inception in `expand_history_df`), then sliced | Not rebased |
| Portfolio | `portfolio_tab.py:31-46` | Absolute `Value` ($); a correct value-ratio `perc_change` is computed but only shown in hover | Plots absolute dollars; no value-weighted lifetime-return line |

Note: `_gen_summary_df` (the table above each dimension chart) already computes a
value-weighted "Lifetime Return (Σ cost basis vs Σ market value)" from
`current_portfolio_summary_df` — so today the dimension **table and chart disagree**.
Approach A makes the chart agree with the table. The summary tables do **not** read
`avg_percent_return`, so the schema change below does not affect them.

## Design

### Data model

Replace the lossy percentage column in each dimension history table with the two dollar
primitives it was derived from:

```
# before
<dim>_history(date, <dim>, avg_percent_return)
# after
<dim>_history(date, <dim>, total_value, total_cost_basis)
```

for `<dim>` in {sectors, asset_types, account_types, geography}.

Add a cost-basis column to the portfolio history table:

```
portfolio_history(date, value)              ->  portfolio_history(date, value, cost_basis)
```

`assets_history` already stores `value` and `cost_basis` — no change.

**Decision D1 — replace, not keep alongside.** `avg_percent_return` is fully derivable from
the new columns, so retaining it is redundant state that can drift. Replace it. A one-time
re-derivation from `assets_history` (already current to 2026-06-14) repopulates the tables.

### Aggregation (`gen_aggregated_historical_value`, helpers.py:~522)

```python
# before: expanded_df.groupby(['Date', dim])['PercentReturn'].mean()  -> AvgPercentReturn
agg = (expanded_df
       .groupby(['Date', dim])
       .agg(total_value=('Value', 'sum'),
            total_cost_basis=('CostBasis', 'sum'))
       .reset_index())
```

Returns `Date, <Dim>, total_value, total_cost_basis`. The four dimension handlers
(`set_history` insert + `get_history` columns) and the `sql.py` create/insert/read
definitions update to match.

### Derived series (display time)

Define one canonical curve per series from the stored dollars:

```
L(t) = (total_value(t) − total_cost_basis(t)) / total_cost_basis(t) × 100      # value-weighted lifetime return
```

- **Lifetime selected** → plot `L(t)`.
- **Window [t₀, t₁] selected** → slice to the window, then per series rebase to its own
  window-start value:

```
y(t) = total_value(t) / total_value(t₀) − 1            # t₀ = first row in the window, per <dim>/Symbol
```

For dimension charts the per-series rebase is `groupby(<dim>)['total_value'].transform('first')`.

**Decision D2 — accept the lifetime/window metric seam.** Lifetime uses return-on-cost-basis;
windows use value-ratio. They coincide only when no money enters/leaves within the window.
This matches existing app behavior (summary table = cost-basis return; milestone cards =
value-ratio) and is the seam Approach C (TWR) would later unify. Documented, not fixed here.

### Per-chart changes

**Dimension charts** (`dimension_tab_factory.py`): callback derives `y` from
`total_value`/`total_cost_basis` per the formulas above instead of reading
`AvgPercentReturn`.

**Per-asset charts** (`assets_tab.py`): after the interval slice, rebase against the
windowed first row instead of plotting the inception-based `ClosingPrice % Change`. Use
value-ratio on `Value` (consistent with dimensions) for the window; `% Change` precompute
in `expand_history_df` may remain for the Lifetime view or be removed if unused.

**Portfolio chart** (`portfolio_tab.py`): plot the rebased percentage line. With the new
`cost_basis` column, the Lifetime view becomes a value-weighted return-on-capital line
(`L(t)`), and window views use the value-ratio already computed at lines 38-40.
`PortfolioHistoryHandler` aggregates `cost_basis` alongside `value` (sum over
`assets_history` per date).

**Demo handler** (`DemoDashboardHandler.py:461-467`): currently synthesizes an
`AvgPercentReturn` column; update to synthesize `total_value`/`total_cost_basis` so demo
mode matches the real schema.

### Scope (Decision D3)

Approved: **all three chart families + portfolio cost basis.** Dimensions carry the schema
+ aggregation work; assets need only a callback change (data already present); portfolio
gets window-rebasing plus a new `cost_basis` column for the value-weighted lifetime line.

## Migration / re-derivation

1. Alter the four dimension tables and `portfolio_history` (add columns / drop
   `avg_percent_return`). For a dev DB, dropping and letting the handlers recreate +
   backfill is acceptable.
2. Re-derive history from `assets_history` via the handlers' `set_history` (cheap; source
   data current to 2026-06-14).
3. Verify max dates and value-weighted figures against `_gen_summary_df` (they should now
   match for the Lifetime view).

## Testing

- Unit: `gen_aggregated_historical_value` returns summed value/cost basis; value-weighted
  `L(t)` for Biotech equals 81.9% on 2026-06-14 (real fixture or synthetic equivalent).
- Unit: window rebase formula — a known two-point series rebases to 0% at t₀ and to the
  multiplicative result at t₁ (e.g. 3.25×→3.75× → 15.4%).
- Unit: per-series rebase rezeroes each dimension independently (every line starts at 0).
- Integration: dimension chart callback Lifetime figure matches the summary table's
  Lifetime Return per dimension.
- Smoke: drive each chart type via the dashboard for Lifetime + a short window; confirm
  window lines start at 0%.

## Out of scope / future

- **Approach C (time-weighted return):** chaining daily returns to neutralize within-window
  contributions, closing the D2 seam. Justified only at 6m+ windows (1w/1m have zero trades
  in this portfolio) and would require re-deriving milestone cards for consistency.
- Unrelated refactors of the dimension handlers beyond the column change.

## Affected files

- `libraries/db/sql.py` — 4 dimension table create/insert/read defs; `portfolio_history` create/insert/read.
- `libraries/helpers.py` — `gen_aggregated_historical_value`.
- `libraries/HistoryHandlers/{Sector,AssetType,AccountType,Geography}HistoryHandler.py` — set/get.
- `libraries/HistoryHandlers/PortfolioHistoryHandler.py` — aggregate + store `cost_basis`.
- `visualization/dash/portfolio_dashboard/tabs/dimension_tab_factory.py` — chart derive.
- `visualization/dash/portfolio_dashboard/tabs/assets_tab.py` — window rebase.
- `visualization/dash/portfolio_dashboard/tabs/portfolio_tab.py` — plot rebased / value-weighted line.
- `visualization/dash/DashboardHandler.py` — `expand_history_df` if asset `% Change` precompute changes.
- `visualization/dash/DemoDashboardHandler.py` — synthesize new columns.

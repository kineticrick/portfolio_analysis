# Assets-tab per-account chart

**Date:** 2026-06-22
**Status:** Approved (design)

## Goal

On the Assets tab, the holdings **table** is already per-account (a symbol held in two
account types shows two rows), but the history **chart** draws one line per *symbol* (the
per-symbol total). Now that `assets_history` stores per-account data
(`assets_history_by_account_df`), make the chart draw **one line per `(symbol,
account_type)`** — so a symbol's true history in each account is visible (e.g. QQQ —
Discretionary and QQQ — Retirement as two lines).

Decision (confirmed): **always per-account** — every line is a `(symbol, account)` series.
**color = ticker, line_dash = account** (a ticker's two accounts share a color; dash
distinguishes the account).

This is the UI follow-up to the per-account `assets_history` storage work; the data
foundation already exists.

## Architecture

### 1. Precomputed per-account expanded frame — `DashboardHandler.__init__`

Add `self.portfolio_assets_history_by_account_expanded_df`: the per-account history
restricted to current-portfolio symbols, with asset info (`Name`, `Sector`) attached:

```python
by_account = self.assets_history_by_account_df.loc[
    self.assets_history_by_account_df['Symbol'].isin(portfolio_symbols)]
self.portfolio_assets_history_by_account_expanded_df = add_asset_info(by_account.copy())
```

`add_asset_info` merges entity columns by `Symbol` and preserves the `AccountType` column.
The `% change` is **not** precomputed here — it is rebased per `(Symbol, AccountType)` in
the chart helper (a per-symbol precompute would be wrong for multi-account tickers and is
overwritten anyway). The existing per-symbol `portfolio_assets_history_expanded_df` is left
untouched (the chat asset-chart still uses it).

Resulting columns: `Date, Symbol, AccountType, Quantity, CostBasis, ClosingPrice, Value,
PercentReturn, Name, Sector, AssetType, Geography`.

### 2. Pure chart-data helper (testable) — `visualization/dash/portfolio_dashboard/tabs/assets_tab.py`

Extract the chart's data shaping from the Dash callback into a pure function:

```python
def prepare_per_account_chart_df(expanded_df, summary_df, selected_pairs, interval,
                                 performance_milestones):
    """Return a frame ready for px.line: per-(Symbol, AccountType) rows over the
    interval, with a live 'today' end-point and a rebased 'ClosingPrice % Change'.
    selected_pairs: set of (Symbol, AccountType) tuples, or empty/None for all."""
```

Responsibilities (moved verbatim from the current callback, generalized to per-account):
- Filter to `selected_pairs` when non-empty (else keep all).
- Append a live "today" end-point per `(Symbol, AccountType)`, taking that account's
  `Current Price`/`Current Value` from `summary_df` (which is per-account — no summing).
- Apply the interval window (`Lifetime` = full history).
- Rebase `ClosingPrice` to the window start **per `[Symbol, AccountType]` group** →
  `ClosingPrice % Change` (reusing `rebase_to_window_start`).

The callback becomes thin: read `DASH_HANDLER.portfolio_assets_history_by_account_expanded_df`,
build `selected_pairs` from `selectedRows` (`{(r['Symbol'], r['AccountType']) for r in
selected_rows}`), call the helper, then render.

### 3. Rendering (the callback)

```python
fig = px.line(
    df, x='Date', y='ClosingPrice % Change',
    color='Symbol', line_dash='AccountType',
    hover_data={'Value': ':$,.2f', 'AccountType': True,
                'ClosingPrice % Change': ':.2f%'},
)
```

`color='Symbol'` (a ticker's accounts share a color), `line_dash='AccountType'` (replaces
the current `line_dash='Sector'`; sector remains available via hover/`Name`). Empty-data
guard unchanged. Height/`ticksuffix` unchanged.

### 4. Selection semantics

`selectedRows` already include `AccountType` (the table `rowData` is per-account). Selecting
"QQQ Retirement" → only that line; selecting both QQQ rows → both lines; no selection → all
`(symbol, account)` series.

### 5. Demo-mode parity — `DemoDashboardHandler.__init__`

Demo's `portfolio_assets_history_df` is per-symbol (no `AccountType`). Add
`portfolio_assets_history_by_account_expanded_df` by attaching each demo symbol's single
`AccountType` (from the existing symbol→account map / `DEMO_ASSETS`) and then
`add_asset_info`. Demo symbols are single-account, so each renders as one line labeled with
its account. This preserves `python portfolio_dashboard.py --demo`.

## Data contracts

- New: `DashboardHandler.portfolio_assets_history_by_account_expanded_df` /
  `DemoDashboardHandler.portfolio_assets_history_by_account_expanded_df` — per
  `(Date, Symbol, AccountType)`, with `ClosingPrice`, `Value`, and entity columns.
- `prepare_per_account_chart_df(...)` returns the same frame plus `ClosingPrice % Change`,
  filtered/windowed, with a live today row per `(Symbol, AccountType)`.
- Unchanged: `portfolio_assets_history_expanded_df` (per-symbol, used by the chat asset
  chart); the holdings table (`assets_summary_df`).

## Testing

- **Pure helper** (`prepare_per_account_chart_df`), synthetic per-account frame:
  - A multi-account symbol yields one series per `(Symbol, AccountType)` (e.g. two QQQ
    lines); `selected_pairs` filters to the chosen account(s); empty selection keeps all.
  - `ClosingPrice % Change` rebases per `(Symbol, AccountType)` (each line starts at 0%).
  - The live today row is appended per account with that account's price/value.
  - Interval windowing drops earlier dates.
- **Real handler** (real DB): `portfolio_assets_history_by_account_expanded_df` has an
  `AccountType` column and a known multi-account symbol (QQQ) has two `(Symbol,
  AccountType)` groups.
- **Demo handler**: constructing `DemoDashboardHandler` exposes
  `portfolio_assets_history_by_account_expanded_df` with an `AccountType` column (one
  account per symbol).
- Existing Assets-tab import / chat / suite stay green.

## Out of scope

- No change to the holdings table (already per-account).
- No new per-account controls/toggles (the breakdown is always-on, per decision).
- No change to the per-symbol chat asset chart.

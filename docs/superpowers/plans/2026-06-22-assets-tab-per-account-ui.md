# Assets-tab per-account chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Assets-tab history chart draw one line per `(symbol, account_type)` — color = ticker, dash = account — using the per-account history.

**Architecture:** Extract the chart's data shaping into a pure, import-safe helper (`prepare_per_account_chart_df`); precompute a per-account expanded history frame on both the real and demo handlers; rewrite the Assets-tab callback to call the helper, color by `Symbol`, dash by `AccountType`, and select by `(Symbol, AccountType)`.

**Tech Stack:** Python 3.13, pandas, Plotly Express, Dash (dash-ag-grid), unittest.

## Global Constraints

- Tests use `unittest`, run via `python -m unittest <module> -v`. NOT pytest.
- `account_type` values: `Discretionary`, `Retirement`. Demo symbols are single-account.
- The pure helper must live OUTSIDE `visualization/dash/portfolio_dashboard/tabs/` — importing anything under `tabs/` runs `tabs/__init__.py`, which constructs the live `DASH_HANDLER` (DB/yfinance). Put it in `visualization/dash/assets_chart_helpers.py` (namespace package; no heavy `__init__`).
- Do NOT change `portfolio_assets_history_expanded_df` (per-symbol; used by the chat asset chart) or the holdings table.
- Chart styling: `color='Symbol'`, `line_dash='AccountType'` (replaces `line_dash='Sector'`).
- `current_portfolio_summary_df` is per-account and has columns `Symbol, AccountType, 'Current Price', 'Current Value'`.
- Activate the venv before running tests: `source venv/bin/activate`.
- Commit message trailers (every commit), exactly:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c
  ```
- Work on branch `assets-tab-per-account-ui` (already checked out). Do NOT switch branches.

---

## File Structure

- `visualization/dash/assets_chart_helpers.py` — NEW. Pure `prepare_per_account_chart_df`. Import-safe.
- `visualization/dash/DashboardHandler.py` — add `_build_by_account_expanded` + precompute `portfolio_assets_history_by_account_expanded_df`.
- `visualization/dash/DemoDashboardHandler.py` — precompute the same attribute from per-symbol demo history + account map.
- `visualization/dash/portfolio_dashboard/tabs/assets_tab.py` — rewrite the chart callback to use the helper + per-account frame; drop now-unused imports.
- `tests/libraries/test_assets_chart_helpers.py` — NEW. Pure helper tests.
- `tests/libraries/test_assets_per_account_ui.py` — NEW. Handler unit test (mocked), demo construction test, demo tab-callback integration.

---

### Task 1: Pure `prepare_per_account_chart_df` helper

**Files:**
- Create: `visualization/dash/assets_chart_helpers.py`
- Test: `tests/libraries/test_assets_chart_helpers.py`

**Interfaces:**
- Consumes: `libraries.returns.rebase_to_window_start(values: pd.Series) -> pd.Series`.
- Produces: `prepare_per_account_chart_df(expanded_df, summary_df, selected_pairs, interval, performance_milestones) -> pd.DataFrame` — per-`(Symbol, AccountType)` rows over the interval, with a live `today` end-point per account and a rebased `ClosingPrice % Change` column.

- [ ] **Step 1: Write the failing test**

Create `tests/libraries/test_assets_chart_helpers.py`:

```python
import datetime
import unittest

import pandas as pd

from visualization.dash.assets_chart_helpers import prepare_per_account_chart_df


def _expanded():
    old = datetime.date(2026, 1, 1)
    mid = datetime.date(2026, 6, 1)
    rows = [
        (old, "QQQ", "Discretionary", 100.0, 1000.0),
        (mid, "QQQ", "Discretionary", 110.0, 1100.0),
        (old, "QQQ", "Retirement", 100.0, 500.0),
        (mid, "QQQ", "Retirement", 110.0, 550.0),
        (old, "AAA", "Discretionary", 50.0, 500.0),
        (mid, "AAA", "Discretionary", 60.0, 600.0),
    ]
    return pd.DataFrame(rows, columns=["Date", "Symbol", "AccountType",
                                       "ClosingPrice", "Value"])


def _summary():
    return pd.DataFrame({
        "Symbol": ["QQQ", "QQQ", "AAA"],
        "AccountType": ["Discretionary", "Retirement", "Discretionary"],
        "Current Price": [120.0, 120.0, 65.0],
        "Current Value": [1200.0, 600.0, 650.0],
    })


_MILESTONES = [("1d", 1), ("1m", 30), ("6m", 180), ("1y", 365)]


class TestPreparePerAccountChartDf(unittest.TestCase):
    def test_all_pairs_when_no_selection(self):
        out = prepare_per_account_chart_df(
            _expanded(), _summary(), None, "Lifetime", _MILESTONES)
        pairs = set(map(tuple, out[["Symbol", "AccountType"]].drop_duplicates()
                        .to_records(index=False)))
        self.assertEqual(
            pairs,
            {("QQQ", "Discretionary"), ("QQQ", "Retirement"),
             ("AAA", "Discretionary")})

    def test_selected_pairs_filter(self):
        out = prepare_per_account_chart_df(
            _expanded(), _summary(), {("QQQ", "Retirement")}, "Lifetime",
            _MILESTONES)
        self.assertEqual(set(out["Symbol"]), {"QQQ"})
        self.assertEqual(set(out["AccountType"]), {"Retirement"})

    def test_rebase_per_account_starts_at_zero(self):
        out = prepare_per_account_chart_df(
            _expanded(), _summary(), None, "Lifetime", _MILESTONES)
        for _, g in out.groupby(["Symbol", "AccountType"]):
            g = g.sort_values("Date")
            self.assertAlmostEqual(g["ClosingPrice % Change"].iloc[0], 0.0)

    def test_today_point_uses_per_account_summary(self):
        out = prepare_per_account_chart_df(
            _expanded(), _summary(), {("QQQ", "Retirement")}, "Lifetime",
            _MILESTONES)
        today = pd.Timestamp("today").normalize()
        last = out[out["Date"] == today]
        self.assertEqual(len(last), 1)
        self.assertAlmostEqual(float(last["ClosingPrice"].iloc[0]), 120.0)
        # 120 / 100 - 1 = 20%
        self.assertAlmostEqual(float(last["ClosingPrice % Change"].iloc[0]), 20.0)

    def test_interval_window_drops_old_dates(self):
        full = prepare_per_account_chart_df(
            _expanded(), _summary(), {("AAA", "Discretionary")}, "Lifetime",
            _MILESTONES)
        windowed = prepare_per_account_chart_df(
            _expanded(), _summary(), {("AAA", "Discretionary")}, "1d",
            _MILESTONES)
        self.assertLess(len(windowed), len(full))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.test_assets_chart_helpers -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'visualization.dash.assets_chart_helpers'`.

- [ ] **Step 3: Implement the helper**

Create `visualization/dash/assets_chart_helpers.py`:

```python
"""Pure data shaping for the Assets-tab per-account history chart.

Kept OUT of the tabs/ package so it imports without constructing DASH_HANDLER.
"""
import pandas as pd
from pandas.tseries.offsets import DateOffset

from libraries.returns import rebase_to_window_start


def prepare_per_account_chart_df(expanded_df, summary_df, selected_pairs,
                                 interval, performance_milestones):
    """Shape per-account asset history for the Assets chart.

    Args:
        expanded_df: per-(Date, Symbol, AccountType) rows incl. ClosingPrice, Value.
        summary_df: current per-account summary incl. Symbol, AccountType,
            'Current Price', 'Current Value'.
        selected_pairs: iterable of (Symbol, AccountType) tuples, or None/empty
            to keep all.
        interval: e.g. '6m' or 'Lifetime'.
        performance_milestones: list of (interval, days) tuples.

    Returns a DataFrame with a rebased 'ClosingPrice % Change' column, a live
    'today' end-point per (Symbol, AccountType), and the interval window applied.
    """
    df = expanded_df.copy()
    df['Date'] = pd.to_datetime(df['Date'])

    if selected_pairs:
        keep = set(selected_pairs)
        df = df[[(s, a) in keep
                 for s, a in zip(df['Symbol'], df['AccountType'])]]

    # Append today's live point per (Symbol, AccountType) so each line ends at
    # that account's live price/value (history excludes today).
    today = pd.Timestamp('today').normalize()
    summ = summary_df.set_index(['Symbol', 'AccountType'])
    today_rows = []
    for (sym, acct), g in df.groupby(['Symbol', 'AccountType']):
        if (sym, acct) in summ.index:
            row = g.sort_values('Date').iloc[-1].copy()
            row['Date'] = today
            row['ClosingPrice'] = float(summ.loc[(sym, acct), 'Current Price'])
            row['Value'] = float(summ.loc[(sym, acct), 'Current Value'])
            today_rows.append(row)
    if today_rows:
        df = pd.concat([df, pd.DataFrame(today_rows)], ignore_index=True)

    if interval != 'Lifetime':
        days = {k: v for (k, v) in performance_milestones}.get(interval, 365)
        start_date = (pd.to_datetime('today') - DateOffset(days=days)).normalize()
        df = df[df['Date'] >= start_date]

    if df.empty:
        return df

    # Rebase each (Symbol, AccountType) line to its window start -> starts at 0%.
    df = df.sort_values(['Symbol', 'AccountType', 'Date'])
    df['ClosingPrice % Change'] = df.groupby(['Symbol', 'AccountType'])[
        'ClosingPrice'].transform(rebase_to_window_start)
    return df
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.test_assets_chart_helpers -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add visualization/dash/assets_chart_helpers.py tests/libraries/test_assets_chart_helpers.py
git commit -m "Add pure prepare_per_account_chart_df helper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 2: Precompute the per-account expanded frame on `DashboardHandler`

**Files:**
- Modify: `visualization/dash/DashboardHandler.py` (add a method near `expand_history_df`; call it in `__init__` after line 61)
- Test: `tests/libraries/test_assets_per_account_ui.py` (create)

**Interfaces:**
- Consumes: `self.assets_history_by_account_df` (per-account, exists); module-level `add_asset_info`.
- Produces: `DashboardHandler._build_by_account_expanded(portfolio_symbols) -> pd.DataFrame`; `self.portfolio_assets_history_by_account_expanded_df` set in `__init__`.

- [ ] **Step 1: Write the failing test**

Create `tests/libraries/test_assets_per_account_ui.py`:

```python
import datetime
import unittest
from unittest import mock

import pandas as pd

from visualization.dash.DashboardHandler import DashboardHandler


class TestBuildByAccountExpanded(unittest.TestCase):
    def _by_account(self):
        d = datetime.date(2026, 6, 1)
        return pd.DataFrame({
            "Date": [d, d, d],
            "Symbol": ["QQQ", "QQQ", "ZZZ"],
            "AccountType": ["Discretionary", "Retirement", "Discretionary"],
            "ClosingPrice": [110.0, 110.0, 5.0],
            "Value": [1100.0, 550.0, 50.0],
        })

    def test_filters_to_portfolio_symbols_and_keeps_accounts(self):
        h = object.__new__(DashboardHandler)   # skip heavy __init__
        h.assets_history_by_account_df = self._by_account()
        with mock.patch(
                "visualization.dash.DashboardHandler.add_asset_info",
                side_effect=lambda df: df):
            out = h._build_by_account_expanded(["QQQ"])
        self.assertEqual(set(out["Symbol"]), {"QQQ"})            # ZZZ filtered out
        self.assertEqual(out["AccountType"].nunique(), 2)        # both accounts kept
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.test_assets_per_account_ui.TestBuildByAccountExpanded -v`
Expected: FAIL — `AttributeError: 'DashboardHandler' object has no attribute '_build_by_account_expanded'`.

- [ ] **Step 3: Add the method and call it in `__init__`**

In `visualization/dash/DashboardHandler.py`, add a method right after `expand_history_df` (it ends at line 447):

```python
    def _build_by_account_expanded(self, portfolio_symbols):
        """Per-account asset history (current holdings) with entity info attached.
        One row per (Date, Symbol, AccountType); feeds the per-account Assets
        chart. % change is rebased per line in the chart helper, not here.
        """
        by_account = self.assets_history_by_account_df.loc[
            self.assets_history_by_account_df['Symbol'].isin(portfolio_symbols)]
        return add_asset_info(by_account.copy())
```

Then in `__init__`, immediately after the existing expanded precompute (line 61, `self.portfolio_assets_history_expanded_df = self.expand_history_df(...)`), add:

```python
        # Per-account expanded history for the per-account Assets chart.
        self.portfolio_assets_history_by_account_expanded_df = \
            self._build_by_account_expanded(portfolio_symbols)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.test_assets_per_account_ui.TestBuildByAccountExpanded -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add visualization/dash/DashboardHandler.py tests/libraries/test_assets_per_account_ui.py
git commit -m "Precompute per-account expanded asset history on DashboardHandler

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 3: Precompute the per-account expanded frame on `DemoDashboardHandler`

**Files:**
- Modify: `visualization/dash/DemoDashboardHandler.py` (imports; after the existing expanded precompute at lines 351-354)
- Test: `tests/libraries/test_assets_per_account_ui.py` (append)

**Interfaces:**
- Consumes: `self.portfolio_assets_history_df` (per-symbol, no AccountType), `self.current_portfolio_summary_df` (has `Symbol`, `AccountType`), `add_asset_info`.
- Produces: `DemoDashboardHandler.portfolio_assets_history_by_account_expanded_df` (per-account; one account per demo symbol).

- [ ] **Step 1: Write the failing test**

Append to `tests/libraries/test_assets_per_account_ui.py`:

```python
class TestDemoPerAccountExpanded(unittest.TestCase):
    def test_demo_exposes_per_account_expanded(self):
        from visualization.dash.DemoDashboardHandler import DemoDashboardHandler
        h = DemoDashboardHandler()
        df = h.portfolio_assets_history_by_account_expanded_df
        self.assertIn("AccountType", df.columns)
        self.assertTrue(
            set(df["AccountType"].unique()).issubset(
                {"Discretionary", "Retirement"}))
        # one account per (Date, Symbol) in demo (single-account symbols)
        self.assertEqual(int(df.duplicated(subset=["Date", "Symbol"]).sum()), 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.test_assets_per_account_ui.TestDemoPerAccountExpanded -v`
Expected: FAIL — `AttributeError: ... 'portfolio_assets_history_by_account_expanded_df'`.

- [ ] **Step 3: Add the demo precompute**

In `visualization/dash/DemoDashboardHandler.py`, ensure `add_asset_info` is importable. Find the existing `from libraries.helpers import ...` line; if `add_asset_info` is not already in it, add it. If there is no such import, add near the other imports at the top:

```python
from libraries.helpers import add_asset_info
```

Then, immediately after the existing expanded precompute block (after line 354, `print("✓ Expanded asset history precomputed")`), add:

```python
        # Per-account expanded history for the per-account Assets chart. Demo
        # symbols are single-account, so attach each symbol's AccountType from
        # the per-account summary, then add entity info.
        acct_map = self.current_portfolio_summary_df[['Symbol', 'AccountType']]
        by_account = self.portfolio_assets_history_df.merge(
            acct_map, on='Symbol', how='left')
        self.portfolio_assets_history_by_account_expanded_df = \
            add_asset_info(by_account)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.test_assets_per_account_ui.TestDemoPerAccountExpanded -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add visualization/dash/DemoDashboardHandler.py tests/libraries/test_assets_per_account_ui.py
git commit -m "Precompute per-account expanded asset history in demo handler

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 4: Rewrite the Assets-tab chart callback

**Files:**
- Modify: `visualization/dash/portfolio_dashboard/tabs/assets_tab.py` (imports lines 1-11; callback lines 80-149)
- Test: `tests/libraries/test_assets_per_account_ui.py` (append)

**Interfaces:**
- Consumes: `prepare_per_account_chart_df` (Task 1); `DASH_HANDLER.portfolio_assets_history_by_account_expanded_df` (Tasks 2/3); `DASH_HANDLER.current_portfolio_summary_df`; `DASH_HANDLER.performance_milestones`.
- Produces: `update_assets_hist_graph(selected_rows, interval) -> go.Figure` keyed per `(Symbol, AccountType)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/libraries/test_assets_per_account_ui.py`:

```python
class TestAssetsTabCallbackDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ["PORTFOLIO_DEMO_MODE"] = "1"
        from visualization.dash.portfolio_dashboard.tabs import assets_tab
        cls.assets_tab = assets_tab

    def test_no_selection_renders_lines(self):
        import plotly.graph_objs as go
        fig = self.assets_tab.update_assets_hist_graph(None, "Lifetime")
        self.assertIsInstance(fig, go.Figure)
        self.assertGreaterEqual(len(fig.data), 1)

    def test_selected_pair_renders(self):
        import plotly.graph_objs as go
        from visualization.dash.portfolio_dashboard.globals import DASH_HANDLER
        srow = DASH_HANDLER.current_portfolio_summary_df.iloc[0]
        rows = [{"Symbol": srow["Symbol"], "AccountType": srow["AccountType"]}]
        fig = self.assets_tab.update_assets_hist_graph(rows, "Lifetime")
        self.assertIsInstance(fig, go.Figure)
        self.assertGreaterEqual(len(fig.data), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.test_assets_per_account_ui.TestAssetsTabCallbackDemo -v`
Expected: FAIL — the current callback colors by `Symbol`/`line_dash='Sector'` and reads the per-symbol frame; with the new test it still "passes" structurally, so to see a real RED first run it BEFORE editing only to confirm the import path resolves. If it already passes, proceed to Step 3 (the callback rewrite is what this task delivers; the test guards the per-account wiring). Note any ambiguity in the report.

- [ ] **Step 3: Rewrite the imports and callback**

In `visualization/dash/portfolio_dashboard/tabs/assets_tab.py`, replace the top imports (lines 1-11) with (drop the now-unused `DateOffset` and `rebase_to_window_start`; add the helper import):

```python
from dash import callback, dcc, Input, Output, html
import dash_ag_grid as dag
import plotly.express as px
import plotly.graph_objs as go
import pandas as pd

from visualization.dash.portfolio_dashboard.globals import *
from visualization.dash.assets_chart_helpers import prepare_per_account_chart_df

import dash_mantine_components as dmc
```

Replace the entire `update_assets_hist_graph` callback (lines 80-149) with:

```python
@callback(
    Output('assets-history-graph', 'figure'),
    Input('assets-table', 'selectedRows'),
    Input('assets-interval-dropdown', 'value'))
def update_assets_hist_graph(selected_rows, interval):
    try:
        expanded = DASH_HANDLER.portfolio_assets_history_by_account_expanded_df
        selected_pairs = (
            {(r['Symbol'], r['AccountType']) for r in selected_rows}
            if selected_rows else None)

        df = prepare_per_account_chart_df(
            expanded, DASH_HANDLER.current_portfolio_summary_df,
            selected_pairs, interval, DASH_HANDLER.performance_milestones)

        if df.empty:
            return go.Figure().update_layout(
                title="No data available. Select assets from the table above.")

        # color = ticker (a ticker's accounts share a color),
        # dash  = account (distinguishes Discretionary vs Retirement).
        fig = px.line(
            df,
            x='Date',
            y='ClosingPrice % Change',
            color='Symbol',
            line_dash='AccountType',
            hover_data={'Value': ':$,.2f', 'AccountType': True,
                        'ClosingPrice % Change': ':.2f%'},
        )
        fig.update_layout(height=800)
        fig.update_yaxes(ticksuffix="%")
        return fig
    except Exception as e:
        print(f"Error in update_assets_hist_graph: {e}")
        return go.Figure().update_layout(title=f"Error loading chart: {str(e)}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.test_assets_per_account_ui.TestAssetsTabCallbackDemo -v`
Expected: PASS (2 tests; demo handler built once, callback returns figures).

- [ ] **Step 5: Run the broader suite**

Run:
```bash
python -m unittest tests.libraries.test_assets_chart_helpers tests.libraries.test_assets_per_account_ui tests.libraries.chat.test_chat_tab_import -v
```
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add visualization/dash/portfolio_dashboard/tabs/assets_tab.py tests/libraries/test_assets_per_account_ui.py
git commit -m "Render Assets chart per (symbol, account): color ticker, dash account

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 5: Real-handler verification + full regression (controller-run)

> Constructing the real `DashboardHandler` is heavy (DB + yfinance), so this is a
> controller-run verification, not an in-suite test.

**Files:** none (verification only)

- [ ] **Step 1: Verify the real handler exposes a correct per-account frame**

Run:
```bash
source venv/bin/activate && python -c "
from visualization.dash.DashboardHandler import DashboardHandler
h = DashboardHandler()
df = h.portfolio_assets_history_by_account_expanded_df
assert 'AccountType' in df.columns
g = df[df['Symbol']=='QQQ'].groupby('AccountType').ngroups
print('QQQ account groups:', g)
assert g >= 2, 'expected QQQ in 2 accounts'
# per-symbol expanded frame still exists and is unchanged in shape
assert 'AccountType' not in h.portfolio_assets_history_expanded_df.columns
print('OK: per-account expanded frame present; per-symbol frame intact')
" 2>&1 | tail -5
```
Expected: `QQQ account groups: 2` (or more) and `OK: ...`.

- [ ] **Step 2: Full regression**

Run:
```bash
source venv/bin/activate && python -m unittest \
  tests.libraries.test_assets_chart_helpers \
  tests.libraries.test_assets_per_account_ui \
  tests.libraries.test_assets_history \
  tests.libraries.test_account_filtering \
  tests.libraries.test_helpers \
  tests.libraries.test_returns \
  tests.libraries.chat.test_tools \
  tests.libraries.chat.test_config \
  tests.libraries.chat.test_chat_tab_import \
  tests.libraries.chat.test_tools_integration 2>&1 | tail -4
```
Expected: OK.

- [ ] **Step 3: Optional manual smoke**

Launch the dashboard, open the Assets tab, select a multi-account ticker (e.g. QQQ): two lines (same color, different dash) appear. `python visualization/dash/portfolio_dashboard/portfolio_dashboard.py` (or `--demo`).

- [ ] **Step 4: Record completion** in the progress ledger (no commit).

---

## Self-Review

**Spec coverage:**
- Precomputed per-account expanded frame (real) → Task 2. ✓
- Pure chart-data helper (selection by pair, per-group rebase, live today point, interval) → Task 1. ✓
- Rendering color=Symbol / dash=AccountType, selection semantics → Task 4. ✓
- Demo parity → Task 3. ✓
- Untouched per-symbol chat chart + table → not modified (constraints). ✓
- Testing: pure helper, real-handler (mocked unit + controller check), demo, tab integration → Tasks 1-5. ✓

**Type consistency:** `prepare_per_account_chart_df(expanded_df, summary_df, selected_pairs, interval, performance_milestones)` defined Task 1, consumed Task 4. `_build_by_account_expanded(portfolio_symbols)` defined Task 2. The attribute `portfolio_assets_history_by_account_expanded_df` is produced in Tasks 2/3 and consumed in Task 4. `selected_pairs` is a set of `(Symbol, AccountType)` in both helper and callback. ✓

**Placeholder scan:** none — every code step has concrete code/commands. (Task 4 Step 2 documents that the new test may not RED cleanly because the callback function name pre-exists; this is explained, not a placeholder.) ✓

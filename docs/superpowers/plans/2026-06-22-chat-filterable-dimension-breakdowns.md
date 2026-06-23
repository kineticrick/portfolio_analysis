# Chat Filterable Dimension Breakdowns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the chat layer answer dimension-breakdown questions filtered by account type and/or entity attributes (e.g. "top sectors in my discretionary account over the last 6 months"), for both the text breakdown and the dimension line chart.

**Architecture:** Account-type filtering is applied at the transaction level in `build_master_log` (events restricted to `{account_type, 'Agnostic'}`) and threaded through `gen_assets_historical_value` → `gen_aggregated_historical_value` (on-demand, cached). Entity filters (sector/asset_type/geography) are applied as a symbol subset. A single reusable handler seam, `get_filtered_dimension_history`, returns the per-date aggregated time series; a pure `compute_dimension_breakdown` turns it into the text summary, while the chart builder draws it directly. (Refinement of the spec: the seam returns the time series rather than the summary, so the same method serves both the text breakdown and the line chart.)

**Tech Stack:** Python 3.13, pandas, unittest, MySQL (real-DB tests per repo convention), Anthropic tool-calling chat layer.

## Global Constraints

- Tests use the `unittest` framework (repo standard), run via `python -m unittest <module> -v`. NOT pytest.
- Real-DB / yfinance-backed tests are acceptable (repo convention); bound them with a recent `start_date` to limit work. Historical prices are disk-cached.
- `account_type` valid values: `'Discretionary'`, `'Retirement'`. Split/acquisition events carry `AccountType == 'Agnostic'` and apply to every account.
- Filter keys exposed to the model: `account_type`, `sector`, `asset_type`, `geography`. Unknown keys must raise the existing descriptive `ValueError` from `_filter_symbols`.
- Aggregated dataframe columns (from `gen_aggregated_historical_value`): `Date`, `<dimension>`, `total_value`, `total_cost_basis`.
- Commit message trailers (every commit):
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c
  ```
- Work on branch `chat-dimension-filters` (already checked out).

---

## File Structure

- `libraries/helpers.py` — add `account_type` param to `build_master_log`, `gen_assets_historical_value`, `gen_aggregated_historical_value` (+ cache key); add pure `compute_dimension_breakdown`.
- `visualization/dash/DashboardHandler.py` — add `get_filtered_dimension_history` seam (+ import `gen_aggregated_historical_value`).
- `libraries/chat/tools.py` — `get_dimension_breakdown` gains `filters`; `show_history_line` dimension branch gains `filters`; helper `_split_account_and_entity_filters`; `TOOL_SCHEMAS` updated.
- `libraries/chat/config.py` — `SYSTEM_PROMPT` notes filtering is available.
- `tests/libraries/test_account_filtering.py` — new; Tasks 1–4 (compute layer + handler seam).
- `tests/libraries/chat/fakes.py` — add `get_filtered_dimension_history` to the fake handler.
- `tests/libraries/chat/test_tools.py` — extend; Tasks 5–6 (tool routing).
- `tests/libraries/chat/test_config.py` — extend; Task 7 (prompt).

---

### Task 1: `account_type` filter in `build_master_log`

**Files:**
- Modify: `libraries/helpers.py` (function `build_master_log`, starts line 49; the `'Agnostic'` tagging is at lines 138-140; add filter just before `return master_log_df` at line 142)
- Test: `tests/libraries/test_account_filtering.py` (create)

**Interfaces:**
- Produces: `build_master_log(symbols: list = [], account_type: str = None) -> pd.DataFrame`. When `account_type` is set, the returned log contains only rows whose `AccountType` is in `{account_type, 'Agnostic'}`.

- [ ] **Step 1: Write the failing test**

Create `tests/libraries/test_account_filtering.py`:

```python
import unittest

import pandas as pd

from libraries.helpers import build_master_log


class TestBuildMasterLogAccountFilter(unittest.TestCase):
    def test_discretionary_filter_keeps_only_discretionary_and_agnostic(self):
        log = build_master_log(account_type="Discretionary")
        self.assertFalse(log.empty)
        kinds = set(log["AccountType"].dropna().unique())
        # Only the requested account plus account-agnostic (split/acquisition) events.
        self.assertTrue(kinds.issubset({"Discretionary", "Agnostic"}),
                        f"unexpected account types: {kinds}")
        self.assertNotIn("Retirement", kinds)

    def test_no_filter_includes_both_accounts(self):
        log = build_master_log()
        kinds = set(log["AccountType"].dropna().unique())
        self.assertIn("Discretionary", kinds)
        self.assertIn("Retirement", kinds)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.test_account_filtering.TestBuildMasterLogAccountFilter -v`
Expected: FAIL — `build_master_log()` got an unexpected keyword argument `account_type` (first test errors).

- [ ] **Step 3: Add the parameter and filter**

In `libraries/helpers.py`, change the signature (line 49):

```python
def  build_master_log(symbols: list=[], account_type: str=None) -> pd.DataFrame:
```

Then, immediately before the final `return master_log_df` (currently line 142, right after the `'Agnostic'` assignment block), insert:

```python
    # Account-type filtering is applied at the transaction level (per CLAUDE.md):
    # keep this account's own events plus 'Agnostic' events (splits/acquisitions
    # apply to every account). Filtering here — rather than on the per-row
    # AccountType of the computed value series — avoids dropping split-date rows
    # that get tagged 'Agnostic' and ffilled forward.
    if account_type is not None:
        master_log_df = master_log_df[
            master_log_df['AccountType'].isin([account_type, 'Agnostic'])]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.test_account_filtering.TestBuildMasterLogAccountFilter -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add libraries/helpers.py tests/libraries/test_account_filtering.py
git commit -m "Add account_type filter to build_master_log

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 2: Thread `account_type` through value + aggregation functions

**Files:**
- Modify: `libraries/helpers.py` — `gen_assets_historical_value` (signature line 375-378; `build_master_log` call line 400) and `gen_aggregated_historical_value` (signature line 487-490; cache key line 509; `gen_assets_historical_value` call line 512-515)
- Test: `tests/libraries/test_account_filtering.py`

**Interfaces:**
- Consumes: `build_master_log(symbols, account_type)` from Task 1.
- Produces:
  - `gen_assets_historical_value(symbols=[], cadence='daily', start_date=None, include_exit_date=True, account_type=None)`
  - `gen_aggregated_historical_value(dimension, symbols=[], cadence='daily', start_date=None, account_type=None)` — aggregated df `Date, <dimension>, total_value, total_cost_basis`, restricted to `account_type` when set.

- [ ] **Step 1: Write the failing test**

Append to `tests/libraries/test_account_filtering.py`:

```python
from libraries.helpers import gen_aggregated_historical_value


class TestAggregationAccountInvariant(unittest.TestCase):
    """Discretionary + Retirement must reconstitute the full portfolio exactly,
    per (Date, Sector). Proves the account filter neither drops nor double-counts."""

    def test_account_split_sums_to_full(self):
        start = "2026-01-01"
        full = gen_aggregated_historical_value("Sector", start_date=start)
        disc = gen_aggregated_historical_value(
            "Sector", start_date=start, account_type="Discretionary")
        ret = gen_aggregated_historical_value(
            "Sector", start_date=start, account_type="Retirement")

        split = (pd.concat([disc, ret])
                 .groupby(["Date", "Sector"], as_index=False)["total_value"].sum())
        merged = full.merge(split, on=["Date", "Sector"], how="outer",
                            suffixes=("_full", "_split")).fillna(0.0)
        diff = (merged["total_value_full"] - merged["total_value_split"]).abs()
        self.assertTrue((diff < 0.01).all(),
                        f"mismatched rows:\n{merged[diff >= 0.01]}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.test_account_filtering.TestAggregationAccountInvariant -v`
Expected: FAIL — `gen_aggregated_historical_value()` got an unexpected keyword argument `account_type`.

- [ ] **Step 3: Thread the parameter through both functions**

In `gen_assets_historical_value`, change the signature (lines 375-378) to add `account_type`:

```python
def gen_assets_historical_value(symbols: list=[], 
                                cadence: str='daily',
                                start_date: str=None,
                                include_exit_date=True,
                                account_type: str=None) -> pd.DataFrame:
```

And change the `build_master_log` call (line 400) to pass it:

```python
    assets_event_log_df = build_master_log(symbols, account_type=account_type)
```

In `gen_aggregated_historical_value`, change the signature (lines 487-490):

```python
def gen_aggregated_historical_value(dimension: str,
                                    symbols: list=[],
                                    cadence: str='daily',
                                    start_date: str=None,
                                    account_type: str=None) -> pd.DataFrame:
```

Change the cache key (line 509) to include `account_type`:

```python
    cache_key = (tuple(symbols), cadence, str(start_date), account_type)
```

Change the `gen_assets_historical_value` call (lines 512-515) to pass it:

```python
        assets_history_df = gen_assets_historical_value(symbols=symbols,
                                                        cadence=cadence,
                                                        start_date=start_date,
                                                        include_exit_date=False,
                                                        account_type=account_type)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.test_account_filtering.TestAggregationAccountInvariant -v`
Expected: PASS (1 test). May take several seconds on first run (master-log + quantities; prices are cached).

- [ ] **Step 5: Commit**

```bash
git add libraries/helpers.py tests/libraries/test_account_filtering.py
git commit -m "Thread account_type through asset/aggregated value computation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 3: Pure `compute_dimension_breakdown`

**Files:**
- Modify: `libraries/helpers.py` — add function after `gen_aggregated_historical_value` (after line 531)
- Test: `tests/libraries/test_account_filtering.py`

**Interfaces:**
- Consumes: aggregated df `Date, <dimension>, total_value, total_cost_basis`.
- Produces: `compute_dimension_breakdown(aggregated_df, dimension: str, lifetime: bool) -> pd.DataFrame` with columns `[dimension, 'Current Value', 'VW Return']`. Window (`lifetime=False`): `VW Return = (last_value / first_value - 1) * 100`, `Current Value = last_value`. Lifetime (`lifetime=True`): `VW Return = (last_value - last_cost) / last_cost * 100`, `Current Value = last_value`. Empty input → empty df with those columns.

- [ ] **Step 1: Write the failing test**

Append to `tests/libraries/test_account_filtering.py`:

```python
import datetime

from libraries.helpers import compute_dimension_breakdown


class TestComputeDimensionBreakdown(unittest.TestCase):
    def _agg(self):
        return pd.DataFrame({
            "Date": [datetime.date(2026, 1, 1), datetime.date(2026, 6, 1),
                     datetime.date(2026, 1, 1), datetime.date(2026, 6, 1)],
            "Sector": ["Tech", "Tech", "Health", "Health"],
            "total_value": [2000.0, 2500.0, 400.0, 500.0],
            "total_cost_basis": [2000.0, 2000.0, 400.0, 400.0],
        })

    def test_window_uses_rebased_return(self):
        out = compute_dimension_breakdown(self._agg(), "Sector", lifetime=False)
        tech = out[out["Sector"] == "Tech"].iloc[0]
        # 2500 / 2000 - 1 = 25%
        self.assertAlmostEqual(tech["VW Return"], 25.0, places=2)
        self.assertAlmostEqual(tech["Current Value"], 2500.0, places=2)
        self.assertEqual(list(out.columns), ["Sector", "Current Value", "VW Return"])

    def test_lifetime_uses_cost_based_return(self):
        out = compute_dimension_breakdown(self._agg(), "Sector", lifetime=True)
        health = out[out["Sector"] == "Health"].iloc[0]
        # (500 - 400) / 400 = 25%
        self.assertAlmostEqual(health["VW Return"], 25.0, places=2)
        self.assertAlmostEqual(health["Current Value"], 500.0, places=2)

    def test_empty_input_returns_shaped_empty(self):
        empty = pd.DataFrame(
            columns=["Date", "Sector", "total_value", "total_cost_basis"])
        out = compute_dimension_breakdown(empty, "Sector", lifetime=False)
        self.assertTrue(out.empty)
        self.assertEqual(list(out.columns), ["Sector", "Current Value", "VW Return"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.test_account_filtering.TestComputeDimensionBreakdown -v`
Expected: FAIL — `ImportError: cannot import name 'compute_dimension_breakdown'`.

- [ ] **Step 3: Implement the function**

In `libraries/helpers.py`, after `gen_aggregated_historical_value` (after line 531), add:

```python
def compute_dimension_breakdown(aggregated_df: pd.DataFrame, dimension: str,
                                lifetime: bool) -> pd.DataFrame:
    """Collapse an aggregated dimension time series into a per-member summary.

    Input columns: Date, <dimension>, total_value, total_cost_basis.
    Output columns: <dimension>, 'Current Value', 'VW Return'.

    - lifetime=True:  VW Return = (value - cost) / cost * 100   (cost-based)
    - lifetime=False: VW Return = (last_value / first_value - 1) * 100 (rebased)
    Current Value is the latest total_value for the member.
    """
    cols = [dimension, "Current Value", "VW Return"]
    if aggregated_df.empty:
        return pd.DataFrame(columns=cols)

    rows = []
    for member, grp in aggregated_df.sort_values("Date").groupby(dimension):
        last_value = grp["total_value"].iloc[-1]
        if lifetime:
            last_cost = grp["total_cost_basis"].iloc[-1]
            vw_return = (last_value - last_cost) / last_cost * 100 \
                if last_cost else 0.0
        else:
            first_value = grp["total_value"].iloc[0]
            vw_return = (last_value / first_value - 1) * 100 \
                if first_value else 0.0
        rows.append({dimension: member, "Current Value": round(last_value, 2),
                     "VW Return": round(vw_return, 2)})

    return pd.DataFrame(rows, columns=cols)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.test_account_filtering.TestComputeDimensionBreakdown -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add libraries/helpers.py tests/libraries/test_account_filtering.py
git commit -m "Add pure compute_dimension_breakdown summary helper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 4: `DashboardHandler.get_filtered_dimension_history` seam

**Files:**
- Modify: `visualization/dash/DashboardHandler.py` — extend the `libraries.helpers` import (line 14) and add a method (place it next to the other dimension properties, after `geography_summary_df`, around line 185)
- Test: `tests/libraries/test_account_filtering.py`

**Interfaces:**
- Consumes: `gen_aggregated_historical_value(dimension, symbols, start_date, account_type)` from Task 2.
- Produces: `DashboardHandler.get_filtered_dimension_history(dimension, account_type=None, symbols=None, start_date=None) -> pd.DataFrame` returning the aggregated time series (`Date, <dimension>, total_value, total_cost_basis`). `symbols=None` means all holdings.

- [ ] **Step 1: Write the failing test**

Append to `tests/libraries/test_account_filtering.py`:

```python
from unittest import mock

from visualization.dash.DashboardHandler import DashboardHandler


class TestHandlerFilteredSeam(unittest.TestCase):
    def test_forwards_args_and_returns_aggregated_df(self):
        sentinel = pd.DataFrame({"Date": [datetime.date(2026, 1, 1)],
                                 "Sector": ["Tech"], "total_value": [1.0],
                                 "total_cost_basis": [1.0]})
        # Build an instance without running the heavy __init__.
        handler = object.__new__(DashboardHandler)
        with mock.patch(
                "visualization.dash.DashboardHandler.gen_aggregated_historical_value",
                return_value=sentinel) as agg:
            out = handler.get_filtered_dimension_history(
                "Sector", account_type="Discretionary",
                symbols=["AAA"], start_date="2026-01-01")
        agg.assert_called_once_with("Sector", symbols=["AAA"],
                                    start_date="2026-01-01",
                                    account_type="Discretionary")
        self.assertIs(out, sentinel)

    def test_symbols_none_becomes_empty_list(self):
        sentinel = pd.DataFrame()
        handler = object.__new__(DashboardHandler)
        with mock.patch(
                "visualization.dash.DashboardHandler.gen_aggregated_historical_value",
                return_value=sentinel) as agg:
            handler.get_filtered_dimension_history("Sector")
        agg.assert_called_once_with("Sector", symbols=[], start_date=None,
                                    account_type=None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.test_account_filtering.TestHandlerFilteredSeam -v`
Expected: FAIL — `AttributeError: 'DashboardHandler' object has no attribute 'get_filtered_dimension_history'` (and the patched name does not exist yet).

- [ ] **Step 3: Add the import and method**

In `visualization/dash/DashboardHandler.py`, extend the helpers import (line 14):

```python
from libraries.helpers import (get_portfolio_current_value, add_asset_info,
                               gen_aggregated_historical_value)
```

Add the method after the `geography_summary_df` property (around line 185):

```python
    def get_filtered_dimension_history(self, dimension, account_type=None,
                                       symbols=None, start_date=None):
        """Aggregated dimension time series, optionally restricted to one
        account_type and/or a symbol subset. Recomputed on demand (cached in
        gen_aggregated_historical_value). Returns columns:
        Date, <dimension>, total_value, total_cost_basis.
        """
        return gen_aggregated_historical_value(
            dimension, symbols=symbols or [], start_date=start_date,
            account_type=account_type)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.test_account_filtering.TestHandlerFilteredSeam -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add visualization/dash/DashboardHandler.py tests/libraries/test_account_filtering.py
git commit -m "Add get_filtered_dimension_history seam to DashboardHandler

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 5: `get_dimension_breakdown` tool gains `filters`

**Files:**
- Modify: `libraries/chat/tools.py` — add `_split_account_and_entity_filters`; rewrite `get_dimension_breakdown` (lines 97-112); extend its schema entry in `TOOL_SCHEMAS` (lines 261-273); add imports
- Modify: `tests/libraries/chat/fakes.py` — add `get_filtered_dimension_history` to the fake handler
- Test: `tests/libraries/chat/test_tools.py`

**Interfaces:**
- Consumes: `handler.get_filtered_dimension_history(...)` (Task 4) and `compute_dimension_breakdown` (Task 3).
- Produces:
  - `get_dimension_breakdown(handler, dimension, interval="Lifetime", filters=None) -> (text, None)`
  - `_split_account_and_entity_filters(filters) -> (account_type_or_None, entity_filters_dict)`

- [ ] **Step 1: Add the fake handler method**

In `tests/libraries/chat/fakes.py`, inside `class FakeHandler`, add (after `sectors_history_df`, around line 85):

```python
        last_filter_call = None

        def get_filtered_dimension_history(self, dimension, account_type=None,
                                           symbols=None, start_date=None):
            # Record the call so routing tests can assert it was used.
            self.last_filter_call = {
                "dimension": dimension, "account_type": account_type,
                "symbols": symbols, "start_date": start_date}
            return pd.DataFrame({
                "Date": [datetime.date(2026, 1, 1), datetime.date(2026, 6, 1)],
                "Sector": ["Tech", "Tech"],
                "total_value": [2000.0, 2500.0],
                "total_cost_basis": [2000.0, 2000.0],
            })
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/libraries/chat/test_tools.py` (inside `class TestDataTools`):

```python
    def test_dimension_breakdown_with_account_filter_uses_seam(self):
        text, fig = tools.get_dimension_breakdown(
            self.h, dimension="Sector", interval="6m",
            filters={"account_type": "Discretionary"})
        self.assertIsNone(fig)
        # Routed through the filtered seam with the account type forwarded.
        self.assertEqual(self.h.last_filter_call["account_type"], "Discretionary")
        # 2500 / 2000 - 1 = 25%
        self.assertIn("Tech", text)
        self.assertIn("25", text)

    def test_dimension_breakdown_entity_filter_resolves_symbols(self):
        # geography=US matches AAA and BBB (not CCC) in the fake summary df.
        tools.get_dimension_breakdown(
            self.h, dimension="Sector", interval="6m",
            filters={"geography": "US"})
        self.assertEqual(set(self.h.last_filter_call["symbols"]), {"AAA", "BBB"})
        self.assertIsNone(self.h.last_filter_call["account_type"])

    def test_dimension_breakdown_no_filter_uses_cached_path(self):
        # Without filters the fast cached path is used; the seam is NOT called.
        self.h.last_filter_call = None
        text, fig = tools.get_dimension_breakdown(
            self.h, dimension="Sector", interval="Lifetime")
        self.assertIsNone(self.h.last_filter_call)
        self.assertIn("Health", text)

    def test_dimension_breakdown_unknown_filter_key_errors(self):
        text, fig = tools.dispatch(
            self.h, "get_dimension_breakdown",
            {"dimension": "Sector", "filters": {"bogus": "x"}})
        self.assertIn("Unknown filter", text)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m unittest tests.libraries.chat.test_tools.TestDataTools -v`
Expected: FAIL — `get_dimension_breakdown()` got an unexpected keyword argument `filters`.

- [ ] **Step 4: Implement filter splitting + routing**

In `libraries/chat/tools.py`, update the imports near the top (after line 11):

```python
from libraries.chat.config import INTERVALS, DIMENSIONS
from libraries.helpers import compute_dimension_breakdown
import pandas as pd
```

(`import pandas as pd` already exists at the top — do not duplicate it; only add the `compute_dimension_breakdown` import.)

Add a helper above `get_dimension_breakdown` (before line 97):

```python
def _split_account_and_entity_filters(filters):
    """Separate the transaction-level account_type filter from the entity-level
    filters (sector/asset_type/geography). Returns (account_type_or_None, dict)."""
    account_type = filters.get("account_type")
    entity = {k: v for k, v in filters.items() if k != "account_type"}
    return account_type, entity
```

Replace the body of `get_dimension_breakdown` (lines 97-112) with:

```python
def get_dimension_breakdown(handler, dimension, interval="Lifetime", filters=None):
    if not filters:
        # Fast path: unfiltered breakdown straight from cached summary/history.
        summary_attr, history_attr = _DIMENSION_ATTRS[dimension]
        if interval == "Lifetime":
            df = getattr(handler, summary_attr)
            out = df[[dimension, "Current Value", "VW Return"]].copy()
            return out.to_string(index=False), None
        days = {k: v for (k, v) in handler.performance_milestones}[interval]
        start = (pd.to_datetime("today") - pd.DateOffset(days=days)).normalize()
        hist = getattr(handler, history_attr).copy()
        hist["Date"] = pd.to_datetime(hist["Date"])
        window = hist[hist["Date"] >= start].sort_values("Date")
        grp = window.groupby(dimension)["TotalValue"]
        vw = ((grp.last() / grp.first() - 1) * 100).round(2)
        out = vw.reset_index().rename(columns={"TotalValue": "VW Return"})
        return out.to_string(index=False), None

    # Filtered path: recompute from transactions via the handler seam.
    account_type, entity_filters = _split_account_and_entity_filters(filters)
    symbols = None
    if entity_filters:
        symbols = sorted(_filter_symbols(handler, entity_filters))
        if not symbols:
            return "No holdings match those filters.", None

    if interval == "Lifetime":
        start_date = None
    elif interval in INTERVALS:
        days = {k: v for (k, v) in handler.performance_milestones}[interval]
        start_date = (pd.to_datetime("today")
                      - pd.DateOffset(days=days)).normalize()
    else:
        return (f"'{interval}' is not a valid interval. Valid intervals: "
                f"{', '.join(INTERVALS)}."), None

    agg = handler.get_filtered_dimension_history(
        dimension, account_type=account_type, symbols=symbols,
        start_date=start_date)
    if agg.empty:
        return "No holdings match those filters.", None
    out = compute_dimension_breakdown(agg, dimension,
                                      lifetime=(interval == "Lifetime"))
    return out.to_string(index=False), None
```

In `TOOL_SCHEMAS`, replace the `get_dimension_breakdown` entry (lines 261-273) with:

```python
    {
        "name": "get_dimension_breakdown",
        "description": "Value-weighted return and value by a dimension over an "
                       "interval. Optionally filter by account_type, sector, "
                       "asset_type, or geography via `filters`.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dimension": {"type": "string", "enum": DIMENSIONS},
                "interval": {"type": "string", "enum": INTERVALS},
                "filters": {
                    "type": "object",
                    "description": "Optional filters, e.g. "
                                   "{\"account_type\": \"Discretionary\"}.",
                    "properties": {
                        "sector": {"type": "string"},
                        "asset_type": {"type": "string"},
                        "account_type": {"type": "string"},
                        "geography": {"type": "string"},
                    },
                },
            },
            "required": ["dimension"],
        },
    },
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m unittest tests.libraries.chat.test_tools -v`
Expected: PASS (all existing + 4 new).

- [ ] **Step 6: Commit**

```bash
git add libraries/chat/tools.py tests/libraries/chat/fakes.py tests/libraries/chat/test_tools.py
git commit -m "Add filters to get_dimension_breakdown chat tool

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 6: `show_history_line` dimension chart gains `filters`

**Files:**
- Modify: `libraries/chat/tools.py` — `show_history_line` signature + dimension branch (lines 143-185); extend its schema entry (lines 309-324)
- Test: `tests/libraries/chat/test_tools.py`

**Interfaces:**
- Consumes: `handler.get_filtered_dimension_history(...)` (Task 4); `_split_account_and_entity_filters` (Task 5); `chart_builders.build_history_line`.
- Produces: `show_history_line(handler, target_type, targets, interval="Lifetime", filters=None) -> (text, figure_or_None)`. For `target_type='dimension'` with `filters`, the line series is built from the filtered aggregated history.

- [ ] **Step 1: Write the failing test**

Append to `tests/libraries/chat/test_tools.py` (inside `class TestChartTools`):

```python
    def test_show_history_line_dimension_with_filter(self):
        text, fig = tools.show_history_line(
            self.h, target_type="dimension", targets=["Sector"],
            interval="6m", filters={"account_type": "Discretionary"})
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(self.h.last_filter_call["account_type"], "Discretionary")
        self.assertGreaterEqual(len(fig.data), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.chat.test_tools.TestChartTools.test_show_history_line_dimension_with_filter -v`
Expected: FAIL — `show_history_line()` got an unexpected keyword argument `filters`.

- [ ] **Step 3: Implement filtered dimension chart**

In `libraries/chat/tools.py`, change the `show_history_line` signature (line 143):

```python
def show_history_line(handler, target_type, targets, interval="Lifetime",
                      filters=None):
```

Replace the dimension branch (lines 170-183) with:

```python
    if target_type == "dimension":
        if not targets:
            return "targets must contain exactly one dimension name.", None
        if targets[0] not in _DIMENSION_ATTRS:
            return (f"Unknown dimension '{targets[0]}'. "
                    f"Valid: {list(_DIMENSION_ATTRS)}."), None

        if filters:
            account_type, entity_filters = \
                _split_account_and_entity_filters(filters)
            symbols = None
            if entity_filters:
                symbols = sorted(_filter_symbols(handler, entity_filters))
                if not symbols:
                    return "No holdings match those filters.", None
            start_date = None if interval == "Lifetime" else start
            agg = handler.get_filtered_dimension_history(
                targets[0], account_type=account_type, symbols=symbols,
                start_date=start_date)
            if agg.empty:
                return "No holdings match those filters.", None
            df = agg.rename(columns={"total_value": "TotalValue"})
        else:
            summary_attr, history_attr = _DIMENSION_ATTRS[targets[0]]
            df = getattr(handler, history_attr).copy()
            df["Date"] = pd.to_datetime(df["Date"])
            df = df[df["Date"] >= start]

        fig = chart_builders.build_history_line(
            df, label_col=targets[0], value_col="TotalValue",
            title=f"{targets[0]} over {interval}")
        return f"{targets[0]} history over {interval}.", fig
```

(`start` is already computed at the top of `show_history_line`, lines 144-148, before the branches.)

In `TOOL_SCHEMAS`, replace the `show_history_line` entry (lines 309-324) with:

```python
    {
        "name": "show_history_line",
        "description": "Render a rebased % LINE CHART. target_type is 'portfolio', "
                       "'asset' (targets=list of tickers), or 'dimension' "
                       "(targets=[dimension name]). For 'dimension' you may pass "
                       "`filters` (account_type/sector/asset_type/geography).",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_type": {"type": "string",
                                "enum": ["portfolio", "asset", "dimension"]},
                "targets": {"type": "array", "items": {"type": "string"}},
                "interval": {"type": "string", "enum": INTERVALS},
                "filters": {
                    "type": "object",
                    "description": "Only for target_type='dimension'.",
                    "properties": {
                        "sector": {"type": "string"},
                        "asset_type": {"type": "string"},
                        "account_type": {"type": "string"},
                        "geography": {"type": "string"},
                    },
                },
            },
            "required": ["target_type", "targets"],
        },
    },
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.libraries.chat.test_tools -v`
Expected: PASS (all existing + new dimension-filter chart test).

- [ ] **Step 5: Commit**

```bash
git add libraries/chat/tools.py tests/libraries/chat/test_tools.py
git commit -m "Add filters to show_history_line dimension chart

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 7: System prompt advertises filtering

**Files:**
- Modify: `libraries/chat/config.py` — `SYSTEM_PROMPT` (lines 28-40)
- Test: `tests/libraries/chat/test_config.py`

**Interfaces:**
- Produces: `SYSTEM_PROMPT` text that mentions dimension breakdowns/charts can be filtered.

- [ ] **Step 1: Write the failing test**

Append a method to `class TestConfig` in `tests/libraries/chat/test_config.py`:

```python
    def test_system_prompt_mentions_filtering(self):
        lowered = config.SYSTEM_PROMPT.lower()
        self.assertIn("filter", lowered)
        self.assertIn("account_type", lowered)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.libraries.chat.test_config -v`
Expected: FAIL — assertion error (prompt does not mention filtering yet).

- [ ] **Step 3: Update the prompt**

In `libraries/chat/config.py`, add a bullet to `SYSTEM_PROMPT` immediately after the Dimensions line (line 36):

```python
- Dimension breakdowns and dimension line charts can be filtered by \
account_type, sector, asset_type, or geography using the `filters` argument \
(e.g. {"account_type": "Discretionary"}). Use it instead of saying filtering \
is unavailable.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.libraries.chat.test_config -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add libraries/chat/config.py tests/libraries/chat/test_config.py
git commit -m "Tell the model dimension breakdowns support filters

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c"
```

---

### Task 8: Full suite regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the full chat + helpers test modules**

Run:
```bash
python -m unittest \
  tests.libraries.test_account_filtering \
  tests.libraries.chat.test_tools \
  tests.libraries.chat.test_engine \
  tests.libraries.chat.test_chart_builders \
  tests.libraries.chat.test_config \
  tests.libraries.chat.test_provider \
  tests.libraries.test_returns -v
```
Expected: OK (all pass). If any pre-existing test broke, fix before proceeding.

- [ ] **Step 2: Manual smoke (optional, requires ANTHROPIC_API_KEY + DB)**

Run the dashboard, open the Chat tab, ask: "Show me the top sectors from my discretionary account over the last 6 months." Expected: a sector breakdown with returns and no "filtering not supported" apology.

---

## Self-Review

**Spec coverage:**
- Account filter at `build_master_log` → Task 1. ✓
- Thread `account_type` through value/aggregation + cache key → Task 2. ✓
- Entity filters as symbol subset → Task 5 (`_split_account_and_entity_filters` + `_filter_symbols`). ✓
- Reusable handler seam for text + chart → Task 4 (`get_filtered_dimension_history`). ✓
- Text breakdown `filters` + schema → Task 5. ✓
- Dimension line chart `filters` + schema → Task 6. ✓
- System prompt update → Task 7. ✓
- Correctness invariant (Disc + Ret == full) → Task 2. ✓
- Error handling (unknown key, empty result, invalid interval) → Task 5 tests + code. ✓
- Out of scope (`assets_history` INSERT IGNORE bug) → not touched. ✓

**Type consistency:** `get_filtered_dimension_history(dimension, account_type, symbols, start_date)` defined in Task 4, consumed identically in Tasks 5–6 and the fake in Task 5. `compute_dimension_breakdown(aggregated_df, dimension, lifetime)` defined Task 3, consumed Task 5. Aggregated columns `total_value`/`total_cost_basis` consistent across Tasks 2–6; chart renames `total_value`→`TotalValue` to match `build_history_line`'s `value_col`. ✓

**Placeholder scan:** none — all steps carry concrete code and commands. ✓

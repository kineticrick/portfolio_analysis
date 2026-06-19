# Portfolio Chat Intelligence Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a natural-language "Chat" tab to the dashboard that answers retrieval questions about the portfolio (rankings, summaries, filters, dimension breakdowns) and renders charts on the fly, using Claude tool-calling over the existing `DashboardHandler` API.

**Architecture:** Four units with one-way dependencies (UI → engine → (provider, tools) → `DASH_HANDLER`). A thin `LLMProvider` isolates the Anthropic SDK so a local model can be swapped later. Tools dispatch to existing, tested handler methods so chat numbers equal dashboard numbers by construction. Multi-turn context is persisted as a plain-text transcript (JSON-serializable in a `dcc.Store`); tool-call rounds happen within a single engine run and are not persisted.

**Tech Stack:** Python, `anthropic` SDK, Dash + dash-mantine-components, plotly, pandas, `unittest` (existing test framework).

**Spec:** `docs/superpowers/specs/2026-06-19-portfolio-chat-intelligence-layer-design.md`

---

## File Structure

```
libraries/chat/
  __init__.py
  config.py          # MODEL, limits, SYSTEM_PROMPT
  provider.py        # ToolCall, LLMResponse, LLMProvider, AnthropicProvider
  chart_builders.py  # build_history_line, build_ranked_bar  (pure plotly)
  tools.py           # TOOL_SCHEMAS, dispatch(), individual tool functions
  engine.py          # run() — the tool-calling loop
visualization/dash/portfolio_dashboard/tabs/chat_tab.py
visualization/dash/portfolio_dashboard/portfolio_dashboard.py   # register tab + Stores
tests/libraries/chat/__init__.py
tests/libraries/chat/fakes.py            # make_fake_handler(), ScriptedProvider
tests/libraries/chat/test_provider.py
tests/libraries/chat/test_chart_builders.py
tests/libraries/chat/test_tools.py
tests/libraries/chat/test_engine.py
README.md             # document the chat feature + ANTHROPIC_API_KEY
requirements.txt      # add anthropic
```

**Conventions for every task below:**
- Run a single test method: `python -m unittest tests.libraries.chat.test_<name>.<Class>.<method> -v`
- Run all chat tests: `python -m unittest discover -s tests/libraries/chat -p "test_*.py" -v`
- Commit messages must end with these two trailer lines:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c
  ```

---

## Task 1: Package skeleton, dependency, and config

**Files:**
- Modify: `requirements.txt`
- Create: `libraries/chat/__init__.py`
- Create: `libraries/chat/config.py`
- Create: `tests/libraries/chat/__init__.py`
- Create: `tests/libraries/chat/test_config.py`

- [ ] **Step 1: Add the dependency**

Add this line to `requirements.txt` (alphabetical-ish, near the top of third-party deps):

```
anthropic>=0.40.0
```

Then install it:

Run: `source venv/bin/activate && pip install "anthropic>=0.40.0"`
Expected: installs successfully.

- [ ] **Step 2: Create empty package markers**

Create `libraries/chat/__init__.py` with a single line:

```python
"""Natural-language chat intelligence layer over the portfolio dashboard."""
```

Create `tests/libraries/chat/__init__.py` as an empty file (zero bytes).

- [ ] **Step 3: Write the failing test for config**

Create `tests/libraries/chat/test_config.py`:

```python
import unittest
from libraries.chat import config


class TestConfig(unittest.TestCase):
    def test_model_is_sonnet(self):
        self.assertEqual(config.MODEL, "claude-sonnet-4-6")

    def test_limits_are_positive_ints(self):
        self.assertGreater(config.MAX_TOKENS, 0)
        self.assertGreater(config.MAX_TOOL_ITERATIONS, 0)
        self.assertGreater(config.MAX_HISTORY_TURNS, 0)

    def test_system_prompt_mentions_tools_and_no_guessing(self):
        prompt = config.SYSTEM_PROMPT.lower()
        self.assertIn("tool", prompt)
        self.assertIn("guess", prompt)
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `python -m unittest tests.libraries.chat.test_config -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'libraries.chat.config'`

- [ ] **Step 5: Create the config module**

Create `libraries/chat/config.py`:

```python
"""Static configuration for the chat layer."""

# Default model. Swap to "claude-haiku-4-5-20251001" for a cheaper fallback.
MODEL = "claude-sonnet-4-6"

# Max tokens for a single model response.
MAX_TOKENS = 1024

# Safety cap on tool-call rounds within one engine run (prevents runaway loops).
MAX_TOOL_ITERATIONS = 5

# How many prior (user/assistant) turns to keep as conversation context.
MAX_HISTORY_TURNS = 20

# Vocabularies the model is constrained to (mirrors the dashboard).
INTERVALS = ["1d", "1w", "1m", "3m", "6m", "1y", "2y", "3y", "5y", "Lifetime"]
DIMENSIONS = ["Sector", "AssetType", "AccountType", "Geography"]

SYSTEM_PROMPT = """You are a portfolio analysis assistant embedded in a personal \
investing dashboard. You answer questions about the user's holdings, returns, and \
portfolio history.

Rules:
- ALWAYS use the provided tools to fetch data. NEVER guess or invent numbers, \
tickers, or returns. If a tool cannot answer the question, say so plainly.
- Intervals must be one of: 1d, 1w, 1m, 3m, 6m, 1y, 2y, 3y, 5y, Lifetime.
- Dimensions must be one of: Sector, AssetType, AccountType, Geography.
- When the user asks to "show", "chart", "plot", or "graph" something, use a chart \
tool so a figure is rendered.
- Keep prose answers concise and reference the concrete numbers the tools return.
"""
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m unittest tests.libraries.chat.test_config -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt libraries/chat/__init__.py libraries/chat/config.py \
        tests/libraries/chat/__init__.py tests/libraries/chat/test_config.py
git commit -m "$(cat <<'EOF'
Add chat package skeleton, anthropic dep, and config

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c
EOF
)"
```

---

## Task 2: Provider layer (LLM I/O abstraction)

**Files:**
- Create: `libraries/chat/provider.py`
- Create: `tests/libraries/chat/test_provider.py`

The provider isolates the Anthropic SDK. `AnthropicProvider.create()` calls the real
API and cannot be unit-tested offline, so the testable logic lives in a static
`_normalize()` method that converts a raw SDK response into our `LLMResponse`.

- [ ] **Step 1: Write the failing test**

Create `tests/libraries/chat/test_provider.py`:

```python
import unittest
from types import SimpleNamespace

from libraries.chat.provider import AnthropicProvider, LLMResponse, ToolCall


def _block(**kw):
    return SimpleNamespace(**kw)


class TestNormalize(unittest.TestCase):
    def test_text_only_response(self):
        raw = SimpleNamespace(
            content=[_block(type="text", text="Hello there")],
            stop_reason="end_turn",
        )
        result = AnthropicProvider._normalize(raw)
        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.text, "Hello there")
        self.assertEqual(result.tool_calls, [])

    def test_tool_use_response(self):
        raw = SimpleNamespace(
            content=[
                _block(type="text", text="Let me check"),
                _block(type="tool_use", id="tu_1", name="rank_assets",
                       input={"interval": "6m", "count": 5}),
            ],
            stop_reason="tool_use",
        )
        result = AnthropicProvider._normalize(raw)
        self.assertEqual(len(result.tool_calls), 1)
        tc = result.tool_calls[0]
        self.assertEqual(tc, ToolCall(id="tu_1", name="rank_assets",
                                      arguments={"interval": "6m", "count": 5}))
        # Raw content is preserved so the engine can append it to history.
        self.assertEqual(result.raw_assistant_content, raw.content)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.libraries.chat.test_provider -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'libraries.chat.provider'`

- [ ] **Step 3: Implement the provider**

Create `libraries/chat/provider.py`:

```python
"""LLM provider abstraction. AnthropicProvider is the only concrete impl today;
a local-model provider can be added later without touching the engine or tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from libraries.chat import config


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: Optional[str]            # final assistant prose, if any
    tool_calls: list               # list[ToolCall] the model wants run
    stop_reason: str
    raw_assistant_content: list = field(default_factory=list)  # SDK content blocks


class LLMProvider(ABC):
    @abstractmethod
    def create(self, system: str, messages: list, tools: list) -> LLMResponse:
        """Send one request and return a normalized response."""


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str = config.MODEL, max_tokens: int = config.MAX_TOKENS):
        import anthropic
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        self._model = model
        self._max_tokens = max_tokens

    def create(self, system: str, messages: list, tools: list) -> LLMResponse:
        raw = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )
        return self._normalize(raw)

    @staticmethod
    def _normalize(raw) -> LLMResponse:
        text_parts = []
        tool_calls = []
        for block in raw.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=block.input))
        return LLMResponse(
            text="".join(text_parts) or None,
            tool_calls=tool_calls,
            stop_reason=raw.stop_reason,
            raw_assistant_content=raw.content,
        )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest tests.libraries.chat.test_provider -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add libraries/chat/provider.py tests/libraries/chat/test_provider.py
git commit -m "$(cat <<'EOF'
Add LLM provider abstraction with Anthropic implementation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c
EOF
)"
```

---

## Task 3: Chart builders (pure plotly)

**Files:**
- Create: `libraries/chat/chart_builders.py`
- Create: `tests/libraries/chat/test_chart_builders.py`

Pure functions: DataFrame in, plotly `Figure` out. No handler, no LLM. They reuse
`libraries/returns.py` for rebasing so chart lines match the dashboard's math.

- [ ] **Step 1: Write the failing test**

Create `tests/libraries/chat/test_chart_builders.py`:

```python
import unittest
import pandas as pd
import plotly.graph_objs as go

from libraries.chat.chart_builders import build_history_line, build_ranked_bar


class TestChartBuilders(unittest.TestCase):
    def test_history_line_rebases_each_series_to_zero(self):
        df = pd.DataFrame({
            "Date": pd.to_datetime(["2026-01-01", "2026-01-02",
                                    "2026-01-01", "2026-01-02"]),
            "Label": ["AAA", "AAA", "BBB", "BBB"],
            "Value": [100.0, 110.0, 200.0, 180.0],
        })
        fig = build_history_line(df, label_col="Label", value_col="Value",
                                 title="t")
        self.assertIsInstance(fig, go.Figure)
        # Two series, each starting at 0%.
        self.assertEqual(len(fig.data), 2)
        for trace in fig.data:
            self.assertAlmostEqual(trace.y[0], 0.0, places=6)

    def test_ranked_bar_has_one_bar_per_row(self):
        df = pd.DataFrame({"Symbol": ["AAA", "BBB", "CCC"],
                           "Return": [12.5, 8.0, -3.0]})
        fig = build_ranked_bar(df, label_col="Symbol", value_col="Return",
                               title="Top movers")
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 1)
        self.assertEqual(list(fig.data[0].x), ["AAA", "BBB", "CCC"])
        self.assertEqual(list(fig.data[0].y), [12.5, 8.0, -3.0])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.libraries.chat.test_chart_builders -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'libraries.chat.chart_builders'`

- [ ] **Step 3: Implement the chart builders**

Create `libraries/chat/chart_builders.py`:

```python
"""Pure plotly figure builders for the chat tab. DataFrame in, Figure out."""

import plotly.express as px
import plotly.graph_objs as go

from libraries.returns import rebase_to_window_start


def build_history_line(df, label_col, value_col, title):
    """Rebased % line chart: each series (grouped by label_col) starts at 0%.

    df must have columns: 'Date', label_col, value_col.
    """
    df = df.sort_values([label_col, "Date"]).copy()
    df["pct"] = df.groupby(label_col)[value_col].transform(rebase_to_window_start)
    fig = px.line(df, x="Date", y="pct", color=label_col, title=title)
    fig.update_yaxes(ticksuffix="%")
    fig.update_layout(height=500)
    return fig


def build_ranked_bar(df, label_col, value_col, title):
    """Simple bar chart, one bar per row, in the order given."""
    fig = go.Figure(go.Bar(x=list(df[label_col]), y=list(df[value_col])))
    fig.update_layout(title=title, height=500)
    fig.update_yaxes(ticksuffix="%")
    return fig
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest tests.libraries.chat.test_chart_builders -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add libraries/chat/chart_builders.py tests/libraries/chat/test_chart_builders.py
git commit -m "$(cat <<'EOF'
Add pure plotly chart builders for the chat tab

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c
EOF
)"
```

---

## Task 4: Test fakes (shared handler + scripted provider)

**Files:**
- Create: `tests/libraries/chat/fakes.py`

A lightweight, DB-free fake handler exposing only the attributes/methods the tools
use, plus a scripted provider for engine tests. Keeping this in one module keeps the
tool/engine tests DRY.

- [ ] **Step 1: Create the fakes module**

Create `tests/libraries/chat/fakes.py`:

```python
"""Test doubles for chat tools and engine — no DB, no network, deterministic."""

import pandas as pd

from libraries.chat.provider import LLMResponse


def make_fake_handler():
    """A stand-in for DashboardHandler with just enough data for the tools."""

    class FakeHandler:
        performance_milestones = [
            ("1d", 1), ("1w", 7), ("1m", 30), ("3m", 90), ("6m", 180),
            ("1y", 365), ("2y", 730), ("3y", 1095), ("5y", 1825),
        ]

        current_portfolio_summary_df = pd.DataFrame({
            "Symbol": ["AAA", "BBB", "CCC"],
            "Name": ["Alpha", "Beta", "Gamma"],
            "Sector": ["Tech", "Tech", "Health"],
            "AssetType": ["Common Stock", "ETF", "Common Stock"],
            "AccountType": ["Discretionary", "Retirement", "Discretionary"],
            "Geography": ["US", "US", "ex-US"],
            "Current Price": [10.0, 20.0, 5.0],
            "Current Value": [1000.0, 2000.0, 500.0],
            "Cost Basis": [800.0, 2200.0, 400.0],
            "Lifetime Return": [25.0, -9.09, 25.0],
            "Dividend Yield": [1.0, 2.0, 0.0],
            "Total Dividend": [10.0, 40.0, 0.0],
        })

        current_portfolio_value = 3500.0

        # Pre-ranked per-interval asset returns (Symbol, Interval, Current Price,
        # Price, Price % Return) — matches get_ranked_assets output columns.
        _asset_milestones = pd.DataFrame({
            "Symbol": ["AAA", "BBB", "CCC", "AAA", "BBB", "CCC"],
            "Interval": ["6m", "6m", "6m", "1y", "1y", "1y"],
            "Current Price": [10.0, 20.0, 5.0, 10.0, 20.0, 5.0],
            "Price": [8.0, 25.0, 4.0, 6.0, 30.0, 3.0],
            "Price % Return": [25.0, -20.0, 25.0, 66.7, -33.3, 66.7],
            "Value % Return": [25.0, -20.0, 25.0, 66.7, -33.3, 66.7],
        })

        def get_ranked_assets(self, interval, price_or_value="price",
                              ascending=False, count=None):
            col = "Price % Return" if price_or_value == "price" else "Value % Return"
            df = self._asset_milestones
            df = df[df["Interval"] == interval].sort_values(col, ascending=ascending)
            if count:
                df = df.head(count)
            return df

        def get_portfolio_milestones(self):
            return pd.DataFrame({
                "Date": pd.to_datetime(["2026-06-12", "2026-06-19"]),
                "Interval": ["6m", "Lifetime"],
                "Value": [3000.0, 3500.0],
                "Percent Return": [16.67, 12.9],
            })

        def get_asset_milestones(self, symbols=None):
            df = self._asset_milestones
            if symbols:
                df = df[df["Symbol"].isin(symbols)]
            return df

        # Dimension summary (Lifetime VW Return lives here).
        sectors_summary_df = pd.DataFrame({
            "Sector": ["Tech", "Health"],
            "Current Value": [3000.0, 500.0],
            "Cost Basis": [3000.0, 400.0],
            "VW Return": [0.0, 25.0],
        })

        # Dimension history (windowed VW Return computed from these dollars).
        sectors_history_df = pd.DataFrame({
            "Date": pd.to_datetime(["2026-01-01", "2026-01-01",
                                    "2026-06-19", "2026-06-19"]),
            "Sector": ["Tech", "Health", "Tech", "Health"],
            "TotalValue": [2400.0, 400.0, 3000.0, 500.0],
            "TotalCostBasis": [3000.0, 400.0, 3000.0, 400.0],
        })

        portfolio_history_df = pd.DataFrame(
            {"Value": [3000.0, 3200.0, 3500.0],
             "CostBasis": [3400.0, 3400.0, 3400.0]},
            index=pd.to_datetime(["2026-01-01", "2026-03-01", "2026-06-19"]),
        )

        portfolio_assets_history_expanded_df = pd.DataFrame({
            "Date": pd.to_datetime(["2026-01-01", "2026-06-19",
                                    "2026-01-01", "2026-06-19"]),
            "Symbol": ["AAA", "AAA", "BBB", "BBB"],
            "ClosingPrice": [8.0, 10.0, 25.0, 20.0],
            "Value": [800.0, 1000.0, 2500.0, 2000.0],
        })

    return FakeHandler()


class ScriptedProvider:
    """Returns pre-scripted LLMResponses in order, ignoring inputs."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, system, messages, tools):
        self.calls.append({"system": system, "messages": messages})
        return self._responses.pop(0)
```

- [ ] **Step 2: Sanity-check it imports**

Run: `python -c "from tests.libraries.chat.fakes import make_fake_handler, ScriptedProvider; print(make_fake_handler().current_portfolio_value)"`
Expected: prints `3500.0`

- [ ] **Step 3: Commit**

```bash
git add tests/libraries/chat/fakes.py
git commit -m "$(cat <<'EOF'
Add test fakes for chat tools and engine

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c
EOF
)"
```

---

## Task 5: Data tools (rank_assets, get_portfolio_summary, get_asset_detail)

**Files:**
- Create: `libraries/chat/tools.py`
- Create: `tests/libraries/chat/test_tools.py`

Each tool function takes `(handler, **arguments)` and returns `(text, figure)` where
`figure` is `None` for data tools. `dispatch()` routes by name and converts any
exception into an error string (so the model can recover). This task creates the
module and the first three data tools; Tasks 6–7 add the rest.

- [ ] **Step 1: Write the failing test**

Create `tests/libraries/chat/test_tools.py`:

```python
import unittest

from libraries.chat import tools
from tests.libraries.chat.fakes import make_fake_handler


class TestDataTools(unittest.TestCase):
    def setUp(self):
        self.h = make_fake_handler()

    def test_rank_assets_top_2_by_price_6m(self):
        text, fig = tools.rank_assets(self.h, interval="6m", count=2)
        self.assertIsNone(fig)
        # Highest first (descending) -> AAA and CCC both 25.0; BBB excluded.
        self.assertIn("AAA", text)
        self.assertNotIn("BBB", text)

    def test_rank_assets_filter_by_account_type(self):
        text, fig = tools.rank_assets(
            self.h, interval="6m", count=5,
            filters={"account_type": "Retirement"})
        # Only BBB is in Retirement.
        self.assertIn("BBB", text)
        self.assertNotIn("AAA", text)

    def test_get_portfolio_summary_interval(self):
        text, fig = tools.get_portfolio_summary(self.h, interval="6m")
        self.assertIsNone(fig)
        self.assertIn("3000", text.replace(",", ""))

    def test_get_asset_detail(self):
        text, fig = tools.get_asset_detail(self.h, symbol="AAA", interval="6m")
        self.assertIn("AAA", text)
        self.assertIn("Discretionary", text)

    def test_dispatch_unknown_tool_returns_error_string(self):
        text, fig = tools.dispatch(self.h, "nope", {})
        self.assertIsNone(fig)
        self.assertIn("Unknown tool", text)

    def test_dispatch_tool_error_is_caught(self):
        # Missing required 'symbol' -> dispatch returns an error string, no raise.
        text, fig = tools.dispatch(self.h, "get_asset_detail", {})
        self.assertIsNone(fig)
        self.assertTrue(text.lower().startswith("error"))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.libraries.chat.test_tools -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'libraries.chat.tools'`

- [ ] **Step 3: Implement tools.py with the first three tools + dispatch**

Create `libraries/chat/tools.py`:

```python
"""Tool functions + schemas + dispatcher for the chat layer.

Each tool: (handler, **arguments) -> (text, figure_or_None).
dispatch() routes by name and converts exceptions into error strings so the model
can recover or ask the user to clarify.
"""

from libraries.chat import chart_builders
from libraries.chat.config import INTERVALS, DIMENSIONS

# Maps a filter key the model uses to the summary-df column name.
_FILTER_COLS = {
    "sector": "Sector",
    "asset_type": "AssetType",
    "account_type": "AccountType",
    "geography": "Geography",
}


def _filter_symbols(handler, filters):
    """Return the set of symbols whose holdings match ALL given filters."""
    df = handler.current_portfolio_summary_df
    for key, value in filters.items():
        col = _FILTER_COLS[key]
        df = df[df[col] == value]
    return set(df["Symbol"])


def rank_assets(handler, interval, count=5, metric="price", ascending=False,
                filters=None):
    ranked = handler.get_ranked_assets(interval, price_or_value=metric,
                                       ascending=ascending)
    if filters:
        keep = _filter_symbols(handler, filters)
        ranked = ranked[ranked["Symbol"].isin(keep)]
    ranked = ranked.head(count)
    cols = ["Symbol", "Interval", "Current Price", "Price % Return"]
    cols = [c for c in cols if c in ranked.columns]
    return ranked[cols].to_string(index=False), None


def get_portfolio_summary(handler, interval="Lifetime"):
    ms = handler.get_portfolio_milestones()
    row = ms[ms["Interval"] == interval]
    if row.empty:
        return f"No portfolio data for interval {interval}.", None
    r = row.iloc[0]
    text = (f"Portfolio at {interval}: value ${r['Value']:,.2f}, "
            f"return {r['Percent Return']:.2f}%. "
            f"Current total value ${handler.current_portfolio_value:,.2f}.")
    return text, None


def get_asset_detail(handler, symbol, interval="Lifetime"):
    summary = handler.current_portfolio_summary_df
    rows = summary[summary["Symbol"] == symbol]
    if rows.empty:
        return f"{symbol} is not currently held.", None
    accounts = ", ".join(sorted(rows["AccountType"].unique()))
    price = rows["Current Price"].iloc[0]
    value = rows["Current Value"].sum()
    lines = [f"{symbol} ({rows['Name'].iloc[0]}) — held in {accounts}.",
             f"Current price ${price:,.2f}, total value ${value:,.2f}.",
             f"Lifetime return {rows['Lifetime Return'].iloc[0]:.2f}%."]
    if interval != "Lifetime":
        ms = handler.get_asset_milestones(symbols=[symbol])
        m = ms[ms["Interval"] == interval]
        if not m.empty:
            lines.append(f"{interval} price return "
                         f"{m['Price % Return'].iloc[0]:.2f}%.")
    return "\n".join(lines), None


# ---- dispatcher ---------------------------------------------------------------

_TOOLS = {
    "rank_assets": rank_assets,
    "get_portfolio_summary": get_portfolio_summary,
    "get_asset_detail": get_asset_detail,
}


def dispatch(handler, name, arguments):
    """Run a tool by name. Returns (text, figure_or_None). Never raises."""
    fn = _TOOLS.get(name)
    if fn is None:
        return f"Unknown tool: {name}", None
    try:
        return fn(handler, **arguments)
    except Exception as exc:  # surfaced back to the model as a tool result
        return f"Error running {name}: {exc}", None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest tests.libraries.chat.test_tools -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add libraries/chat/tools.py tests/libraries/chat/test_tools.py
git commit -m "$(cat <<'EOF'
Add data tools (rank, portfolio summary, asset detail) + dispatcher

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c
EOF
)"
```

---

## Task 6: Remaining data tools (get_dimension_breakdown, filter_holdings)

**Files:**
- Modify: `libraries/chat/tools.py`
- Modify: `tests/libraries/chat/test_tools.py`

- [ ] **Step 1: Add failing tests**

Append these methods to `class TestDataTools` in `tests/libraries/chat/test_tools.py`:

```python
    def test_dimension_breakdown_lifetime_uses_summary_vw(self):
        text, fig = tools.get_dimension_breakdown(
            self.h, dimension="Sector", interval="Lifetime")
        self.assertIsNone(fig)
        self.assertIn("Health", text)
        self.assertIn("25.0", text)  # Health VW Return from summary df

    def test_dimension_breakdown_window_uses_history(self):
        text, fig = tools.get_dimension_breakdown(
            self.h, dimension="Sector", interval="6m")
        # Tech grew 2400 -> 3000 over the window = 25.0%.
        self.assertIn("Tech", text)
        self.assertIn("25.0", text)

    def test_filter_holdings_returns_matches(self):
        text, fig = tools.filter_holdings(
            self.h, filters={"account_type": "Discretionary"})
        self.assertIn("AAA", text)
        self.assertIn("CCC", text)
        self.assertNotIn("BBB", text)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tests.libraries.chat.test_tools.TestDataTools.test_filter_holdings_returns_matches -v`
Expected: FAIL with `AttributeError: module 'libraries.chat.tools' has no attribute 'filter_holdings'`

- [ ] **Step 3: Implement the two tools**

Add to `libraries/chat/tools.py` (before the `# ---- dispatcher` section). The
dimension lookup maps a dimension name to its summary/history attributes:

```python
_DIMENSION_ATTRS = {
    "Sector": ("sectors_summary_df", "sectors_history_df"),
    "AssetType": ("asset_types_summary_df", "asset_types_history_df"),
    "AccountType": ("account_types_summary_df", "account_types_history_df"),
    "Geography": ("geography_summary_df", "geography_history_df"),
}


def get_dimension_breakdown(handler, dimension, interval="Lifetime"):
    summary_attr, history_attr = _DIMENSION_ATTRS[dimension]
    if interval == "Lifetime":
        df = getattr(handler, summary_attr)
        out = df[[dimension, "Current Value", "VW Return"]].copy()
        return out.to_string(index=False), None
    # Window: value-weighted return = TotalValue(end) / TotalValue(start) - 1.
    days = {k: v for (k, v) in handler.performance_milestones}[interval]
    import pandas as pd
    start = (pd.to_datetime("today") - pd.DateOffset(days=days)).normalize()
    hist = getattr(handler, history_attr)
    window = hist[hist["Date"] >= start].sort_values("Date")
    grp = window.groupby(dimension)["TotalValue"]
    vw = ((grp.last() / grp.first() - 1) * 100).round(2)
    out = vw.reset_index().rename(columns={"TotalValue": "VW Return"})
    return out.to_string(index=False), None


def filter_holdings(handler, filters, columns=None):
    keep = _filter_symbols(handler, filters)
    df = handler.current_portfolio_summary_df
    df = df[df["Symbol"].isin(keep)]
    if columns:
        columns = [c for c in columns if c in df.columns]
        df = df[columns]
    else:
        df = df[["Symbol", "Name", "AccountType", "Current Value"]]
    return df.to_string(index=False), None
```

Then register both in the `_TOOLS` dict:

```python
_TOOLS = {
    "rank_assets": rank_assets,
    "get_portfolio_summary": get_portfolio_summary,
    "get_asset_detail": get_asset_detail,
    "get_dimension_breakdown": get_dimension_breakdown,
    "filter_holdings": filter_holdings,
}
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m unittest tests.libraries.chat.test_tools -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add libraries/chat/tools.py tests/libraries/chat/test_tools.py
git commit -m "$(cat <<'EOF'
Add dimension breakdown and filter holdings data tools

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c
EOF
)"
```

---

## Task 7: Chart tools + tool schemas

**Files:**
- Modify: `libraries/chat/tools.py`
- Modify: `tests/libraries/chat/test_tools.py`

Chart tools return `(summary_text, figure)`. Also add the `TOOL_SCHEMAS` list the
provider passes to the model.

- [ ] **Step 1: Add failing tests**

Append a new test class to `tests/libraries/chat/test_tools.py`:

```python
import plotly.graph_objs as go


class TestChartTools(unittest.TestCase):
    def setUp(self):
        self.h = make_fake_handler()

    def test_show_ranked_bar_returns_figure(self):
        text, fig = tools.show_ranked_bar(self.h, interval="6m", count=3)
        self.assertIsInstance(fig, go.Figure)
        self.assertIn("AAA", text)

    def test_show_history_line_portfolio(self):
        text, fig = tools.show_history_line(
            self.h, target_type="portfolio", targets=[], interval="Lifetime")
        self.assertIsInstance(fig, go.Figure)
        self.assertGreaterEqual(len(fig.data), 1)

    def test_show_history_line_assets(self):
        text, fig = tools.show_history_line(
            self.h, target_type="asset", targets=["AAA", "BBB"],
            interval="Lifetime")
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 2)

    def test_tool_schemas_cover_all_tools(self):
        names = {s["name"] for s in tools.TOOL_SCHEMAS}
        self.assertEqual(names, set(tools._TOOLS.keys()))
        for schema in tools.TOOL_SCHEMAS:
            self.assertIn("description", schema)
            self.assertIn("input_schema", schema)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tests.libraries.chat.test_tools.TestChartTools -v`
Expected: FAIL with `AttributeError: module 'libraries.chat.tools' has no attribute 'show_ranked_bar'`

- [ ] **Step 3: Implement chart tools + schemas**

Add the chart tools to `libraries/chat/tools.py` (before the dispatcher section):

```python
def show_ranked_bar(handler, interval, count=5, metric="price", ascending=False,
                    filters=None):
    ranked = handler.get_ranked_assets(interval, price_or_value=metric,
                                       ascending=ascending)
    if filters:
        keep = _filter_symbols(handler, filters)
        ranked = ranked[ranked["Symbol"].isin(keep)]
    ranked = ranked.head(count)
    fig = chart_builders.build_ranked_bar(
        ranked, label_col="Symbol", value_col="Price % Return",
        title=f"{interval} ranked assets")
    summary = ranked[["Symbol", "Price % Return"]].to_string(index=False)
    return summary, fig


def show_history_line(handler, target_type, targets, interval="Lifetime"):
    import pandas as pd
    if interval == "Lifetime":
        start = pd.Timestamp.min
    else:
        days = {k: v for (k, v) in handler.performance_milestones}[interval]
        start = (pd.to_datetime("today") - pd.DateOffset(days=days)).normalize()

    if target_type == "portfolio":
        df = handler.portfolio_history_df.reset_index()
        df = df.rename(columns={df.columns[0]: "Date"})
        df["Label"] = "Portfolio"
        df = df[df["Date"] >= start]
        fig = chart_builders.build_history_line(
            df, label_col="Label", value_col="Value", title="Portfolio history")
        return f"Portfolio history over {interval}.", fig

    if target_type == "asset":
        df = handler.portfolio_assets_history_expanded_df
        df = df[df["Symbol"].isin(targets)]
        df = df[df["Date"] >= start]
        fig = chart_builders.build_history_line(
            df, label_col="Symbol", value_col="ClosingPrice",
            title=f"{', '.join(targets)} over {interval}")
        return f"Price history for {', '.join(targets)} over {interval}.", fig

    if target_type == "dimension":
        summary_attr, history_attr = _DIMENSION_ATTRS[targets[0]]
        df = getattr(handler, history_attr)
        df = df[df["Date"] >= start]
        fig = chart_builders.build_history_line(
            df, label_col=targets[0], value_col="TotalValue",
            title=f"{targets[0]} over {interval}")
        return f"{targets[0]} history over {interval}.", fig

    return f"Unknown target_type: {target_type}", None
```

Register them in `_TOOLS`:

```python
    "show_ranked_bar": show_ranked_bar,
    "show_history_line": show_history_line,
```

Then add the schema list at the end of the file:

```python
TOOL_SCHEMAS = [
    {
        "name": "rank_assets",
        "description": "Rank currently-held assets by return over an interval. "
                       "Returns the top/bottom N as text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "interval": {"type": "string", "enum": INTERVALS},
                "count": {"type": "integer", "default": 5},
                "metric": {"type": "string", "enum": ["price", "value"],
                           "default": "price"},
                "ascending": {"type": "boolean", "default": False},
                "filters": {
                    "type": "object",
                    "description": "Optional dimension filters, e.g. "
                                   "{\"account_type\": \"Retirement\"}.",
                    "properties": {
                        "sector": {"type": "string"},
                        "asset_type": {"type": "string"},
                        "account_type": {"type": "string"},
                        "geography": {"type": "string"},
                    },
                },
            },
            "required": ["interval"],
        },
    },
    {
        "name": "get_portfolio_summary",
        "description": "Total portfolio value and return at an interval.",
        "input_schema": {
            "type": "object",
            "properties": {"interval": {"type": "string", "enum": INTERVALS}},
            "required": [],
        },
    },
    {
        "name": "get_asset_detail",
        "description": "Details for one ticker: price, value, return, accounts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "interval": {"type": "string", "enum": INTERVALS},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_dimension_breakdown",
        "description": "Value-weighted return and value by a dimension over an "
                       "interval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dimension": {"type": "string", "enum": DIMENSIONS},
                "interval": {"type": "string", "enum": INTERVALS},
            },
            "required": ["dimension"],
        },
    },
    {
        "name": "filter_holdings",
        "description": "List holdings matching dimension filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "properties": {
                        "sector": {"type": "string"},
                        "asset_type": {"type": "string"},
                        "account_type": {"type": "string"},
                        "geography": {"type": "string"},
                    },
                },
                "columns": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["filters"],
        },
    },
    {
        "name": "show_ranked_bar",
        "description": "Render a BAR CHART of top/bottom N assets by return.",
        "input_schema": {
            "type": "object",
            "properties": {
                "interval": {"type": "string", "enum": INTERVALS},
                "count": {"type": "integer", "default": 5},
                "metric": {"type": "string", "enum": ["price", "value"]},
                "ascending": {"type": "boolean", "default": False},
                "filters": {"type": "object"},
            },
            "required": ["interval"],
        },
    },
    {
        "name": "show_history_line",
        "description": "Render a rebased % LINE CHART. target_type is 'portfolio', "
                       "'asset' (targets=list of tickers), or 'dimension' "
                       "(targets=[dimension name]).",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_type": {"type": "string",
                                "enum": ["portfolio", "asset", "dimension"]},
                "targets": {"type": "array", "items": {"type": "string"}},
                "interval": {"type": "string", "enum": INTERVALS},
            },
            "required": ["target_type", "targets"],
        },
    },
]
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m unittest tests.libraries.chat.test_tools -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add libraries/chat/tools.py tests/libraries/chat/test_tools.py
git commit -m "$(cat <<'EOF'
Add chart tools and tool schemas

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c
EOF
)"
```

---

## Task 8: Chat engine (tool-calling loop)

**Files:**
- Create: `libraries/chat/engine.py`
- Create: `tests/libraries/chat/test_engine.py`

`run()` builds the message list from the persisted plain-text transcript plus the
new question, loops over provider→tool→provider until the model returns prose, caps
iterations, and collects figures.

- [ ] **Step 1: Write the failing test**

Create `tests/libraries/chat/test_engine.py`:

```python
import unittest

from libraries.chat import engine, tools
from libraries.chat.provider import LLMResponse, ToolCall
from tests.libraries.chat.fakes import make_fake_handler, ScriptedProvider


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.h = make_fake_handler()

    def test_direct_text_answer_no_tools(self):
        provider = ScriptedProvider([
            LLMResponse(text="Hi!", tool_calls=[], stop_reason="end_turn",
                        raw_assistant_content=[]),
        ])
        text, figs = engine.run(provider, self.h, prior_turns=[],
                                 user_message="hello", view_context={})
        self.assertEqual(text, "Hi!")
        self.assertEqual(figs, [])

    def test_tool_round_then_answer_collects_figure(self):
        provider = ScriptedProvider([
            LLMResponse(text=None, stop_reason="tool_use",
                        tool_calls=[ToolCall(id="t1", name="show_ranked_bar",
                                             arguments={"interval": "6m",
                                                        "count": 2})],
                        raw_assistant_content=[{"type": "tool_use", "id": "t1",
                                                "name": "show_ranked_bar",
                                                "input": {"interval": "6m",
                                                          "count": 2}}]),
            LLMResponse(text="Here is the chart.", tool_calls=[],
                        stop_reason="end_turn", raw_assistant_content=[]),
        ])
        text, figs = engine.run(provider, self.h, prior_turns=[],
                                user_message="top 2 over 6m", view_context={})
        self.assertEqual(text, "Here is the chart.")
        self.assertEqual(len(figs), 1)

    def test_iteration_cap(self):
        # Always asks for a tool -> engine must stop and not loop forever.
        def tool_resp():
            return LLMResponse(
                text=None, stop_reason="tool_use",
                tool_calls=[ToolCall(id="t", name="get_portfolio_summary",
                                     arguments={})],
                raw_assistant_content=[{"type": "tool_use", "id": "t",
                                        "name": "get_portfolio_summary",
                                        "input": {}}])
        provider = ScriptedProvider([tool_resp() for _ in range(10)])
        text, figs = engine.run(provider, self.h, prior_turns=[],
                                user_message="loop", view_context={})
        self.assertIn("too many", text.lower())

    def test_prior_turns_included_in_messages(self):
        provider = ScriptedProvider([
            LLMResponse(text="ok", tool_calls=[], stop_reason="end_turn",
                        raw_assistant_content=[]),
        ])
        engine.run(provider, self.h,
                   prior_turns=[{"role": "user", "text": "earlier"}],
                   user_message="now", view_context={})
        sent = provider.calls[0]["messages"]
        self.assertEqual(sent[0], {"role": "user", "content": "earlier"})
        self.assertEqual(sent[-1], {"role": "user", "content": "now"})
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tests.libraries.chat.test_engine -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'libraries.chat.engine'`

- [ ] **Step 3: Implement the engine**

Create `libraries/chat/engine.py`:

```python
"""The tool-calling loop. Pure Python; no Dash, no direct SDK use."""

from libraries.chat import tools
from libraries.chat.config import (SYSTEM_PROMPT, MAX_TOOL_ITERATIONS,
                                   MAX_HISTORY_TURNS)


def _build_system(view_context):
    """Append ambient view context (Level-1 awareness) to the system prompt."""
    if view_context:
        dim = view_context.get("dimension")
        interval = view_context.get("interval")
        if dim or interval:
            return (SYSTEM_PROMPT + f"\n\nThe user is currently viewing: "
                    f"dimension={dim}, interval={interval}. Resolve vague "
                    f"references like 'this' against that context.")
    return SYSTEM_PROMPT


def run(provider, handler, prior_turns, user_message, view_context):
    """Answer one user message. Returns (answer_text, [figures]).

    prior_turns: list of {"role": "user"|"assistant", "text": str}.
    """
    system = _build_system(view_context)
    trimmed = prior_turns[-MAX_HISTORY_TURNS:]
    messages = [{"role": t["role"], "content": t["text"]} for t in trimmed]
    messages.append({"role": "user", "content": user_message})

    figures = []
    for _ in range(MAX_TOOL_ITERATIONS):
        resp = provider.create(system, messages, tools.TOOL_SCHEMAS)
        if not resp.tool_calls:
            return (resp.text or ""), figures

        messages.append({"role": "assistant",
                         "content": resp.raw_assistant_content})
        tool_results = []
        for tc in resp.tool_calls:
            text, fig = tools.dispatch(handler, tc.name, tc.arguments)
            if fig is not None:
                figures.append(fig)
            tool_results.append({"type": "tool_result", "tool_use_id": tc.id,
                                 "content": text})
        messages.append({"role": "user", "content": tool_results})

    return ("I made too many tool calls without finishing — please refine "
            "your question."), figures
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m unittest tests.libraries.chat.test_engine -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the whole chat suite**

Run: `python -m unittest discover -s tests/libraries/chat -p "test_*.py" -v`
Expected: PASS (all tests across config/provider/chart_builders/tools/engine)

- [ ] **Step 6: Commit**

```bash
git add libraries/chat/engine.py tests/libraries/chat/test_engine.py
git commit -m "$(cat <<'EOF'
Add chat engine tool-calling loop

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c
EOF
)"
```

---

## Task 9: Dash Chat tab + wire into the app

**Files:**
- Create: `visualization/dash/portfolio_dashboard/tabs/chat_tab.py`
- Modify: `visualization/dash/portfolio_dashboard/portfolio_dashboard.py`
- Create: `tests/libraries/chat/test_chat_tab_import.py`

Dash callbacks aren't unit-tested here (they need a running server); instead a smoke
test asserts the module imports and exposes the expected layout + Store IDs.

First, read the existing app shell so the new tab follows the established pattern:

Run: `grep -nE "dcc.Tab\(|dcc.Tabs\(|dcc.Store|import|app.layout|tabs=" visualization/dash/portfolio_dashboard/portfolio_dashboard.py`
Use the output to match how existing tabs are imported and added.

- [ ] **Step 1: Write the failing smoke test**

Create `tests/libraries/chat/test_chat_tab_import.py`:

```python
import unittest


class TestChatTabImport(unittest.TestCase):
    def test_module_exposes_layout_and_store_ids(self):
        from visualization.dash.portfolio_dashboard.tabs import chat_tab
        self.assertTrue(hasattr(chat_tab, "chat_tab"))
        self.assertEqual(chat_tab.HISTORY_STORE_ID, "chat-history-store")
        self.assertEqual(chat_tab.THREAD_STORE_ID, "chat-thread-store")
        self.assertEqual(chat_tab.VIEW_CONTEXT_STORE_ID, "view-context-store")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tests.libraries.chat.test_chat_tab_import -v`
Expected: FAIL with `ImportError` / `ModuleNotFoundError` for `chat_tab`

- [ ] **Step 3: Implement the chat tab**

Create `visualization/dash/portfolio_dashboard/tabs/chat_tab.py`:

```python
import os

from dash import callback, dcc, html, Input, Output, State, no_update
import dash_mantine_components as dmc
import plotly.graph_objs as go

from visualization.dash.portfolio_dashboard.globals import *
from libraries.chat import engine
from libraries.chat.provider import AnthropicProvider

HISTORY_STORE_ID = "chat-history-store"
THREAD_STORE_ID = "chat-thread-store"
VIEW_CONTEXT_STORE_ID = "view-context-store"

# One provider instance reused across queries (only constructed if a key exists).
_PROVIDER = None


def _get_provider():
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = AnthropicProvider()
    return _PROVIDER


def _render_thread(thread):
    """Turn the persisted thread (list of dicts) into message components."""
    bubbles = []
    for entry in thread:
        align = "flex-end" if entry["role"] == "user" else "flex-start"
        color = "blue" if entry["role"] == "user" else "gray"
        children = [dcc.Markdown(entry["text"])] if entry.get("text") else []
        for fig_dict in entry.get("figures", []):
            children.append(dcc.Graph(figure=go.Figure(fig_dict)))
        bubbles.append(
            dmc.Paper(children, shadow="xs", p="sm", withBorder=True,
                      style={"alignSelf": align, "maxWidth": "85%",
                             "background": "var(--mantine-color-%s-0)" % color}))
    return dmc.Stack(bubbles, gap="sm")


@callback(
    Output(THREAD_STORE_ID, "data"),
    Output(HISTORY_STORE_ID, "data"),
    Output("chat-input", "value"),
    Input("chat-send", "n_clicks"),
    State("chat-input", "value"),
    State(HISTORY_STORE_ID, "data"),
    State(THREAD_STORE_ID, "data"),
    State(VIEW_CONTEXT_STORE_ID, "data"),
    prevent_initial_call=True,
)
def on_send(n_clicks, user_text, history, thread, view_context):
    if not user_text:
        return no_update, no_update, no_update
    history = history or []
    thread = thread or []

    if not os.environ.get("ANTHROPIC_API_KEY"):
        answer, figures = ("Chat needs an ANTHROPIC_API_KEY environment "
                           "variable to be set.", [])
    else:
        try:
            answer, figs = engine.run(_get_provider(), DASH_HANDLER,
                                      prior_turns=history,
                                      user_message=user_text,
                                      view_context=view_context or {})
            figures = [f.to_dict() for f in figs]
        except Exception as exc:
            answer, figures = (f"Sorry, I hit an error: {exc}", [])

    thread = thread + [{"role": "user", "text": user_text},
                       {"role": "assistant", "text": answer, "figures": figures}]
    history = history + [{"role": "user", "text": user_text},
                         {"role": "assistant", "text": answer}]
    return thread, history, ""


@callback(
    Output("chat-thread", "children"),
    Input(THREAD_STORE_ID, "data"),
)
def render(thread):
    return _render_thread(thread or [])


chat_tab = dmc.Container(
    [
        dcc.Store(id=HISTORY_STORE_ID, data=[]),
        dcc.Store(id=THREAD_STORE_ID, data=[]),
        # Populated by other tabs later (Level-1 awareness seam). Empty for now.
        dcc.Store(id=VIEW_CONTEXT_STORE_ID, data={}),
        dmc.Title("Ask your portfolio", order=2, mb="md"),
        html.Div(id="chat-thread", style={"minHeight": "400px",
                                          "marginBottom": "1rem"}),
        dmc.Group([
            dcc.Input(id="chat-input", type="text", debounce=True,
                      placeholder="e.g. Top 5 assets in my discretionary account "
                                  "over the last 6 months",
                      style={"flex": 1}),
            dmc.Button("Send", id="chat-send"),
        ], align="flex-end"),
    ],
    fluid=True,
)
```

- [ ] **Step 4: Register the tab in the app**

In `visualization/dash/portfolio_dashboard/portfolio_dashboard.py`, following the
exact import + `dcc.Tab` pattern you found in Step's grep:

1. Add the import alongside the other tab imports:

```python
from visualization.dash.portfolio_dashboard.tabs.chat_tab import chat_tab
```

2. Add a new `dcc.Tab` to the `dcc.Tabs` children (append after the existing tabs).
Match the surrounding tabs' `label`/`value` style; for example:

```python
        dcc.Tab(label='Chat', value='chat-dash-tab', children=[chat_tab]),
```

(If the app maps tab `value` → content elsewhere instead of nesting `children`,
follow that pattern instead and register `chat_tab` the same way the other tabs are.)

- [ ] **Step 5: Run the smoke test**

Run: `python -m unittest tests.libraries.chat.test_chat_tab_import -v`
Expected: PASS (1 test)

- [ ] **Step 6: Verify the app boots**

Run: `python -c "import visualization.dash.portfolio_dashboard.portfolio_dashboard"`
Expected: imports without error (no server start). If it starts a server on import,
instead run the app briefly and confirm no traceback, then stop it.

- [ ] **Step 7: Commit**

```bash
git add visualization/dash/portfolio_dashboard/tabs/chat_tab.py \
        visualization/dash/portfolio_dashboard/portfolio_dashboard.py \
        tests/libraries/chat/test_chat_tab_import.py
git commit -m "$(cat <<'EOF'
Add Chat tab and wire it into the dashboard

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c
EOF
)"
```

---

## Task 10: Manual end-to-end check + docs

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Live smoke test (manual)**

With a real key set, start the app and ask a question:

```bash
export ANTHROPIC_API_KEY=...        # user provides
source venv/bin/activate
python visualization/dash/portfolio_dashboard/portfolio_dashboard.py
```

In the browser (http://localhost:8050), open the **Chat** tab and ask:
- "What are the top 3 assets over the last 6 months?" → expect a text ranking.
- "Show me the top 3 assets over the last 6 months" → expect a bar chart to appear.
- "Show my portfolio history over 1y" → expect a rebased line chart.

Confirm: numbers match what the Assets/Portfolio tabs show for the same interval,
and that with no `ANTHROPIC_API_KEY` the tab shows the setup message instead of
crashing.

- [ ] **Step 2: Document the feature in the README**

Add a "Chat / Ask your portfolio" section to `README.md` covering:
- What it does (natural-language retrieval Q&A + on-the-fly charts).
- Setup: `pip install -r requirements.txt` (now includes `anthropic`) and
  `export ANTHROPIC_API_KEY=...`.
- Default model is `claude-sonnet-4-6`; switch to Haiku by editing
  `libraries/chat/config.py` (`MODEL`).
- It is read-only and reuses the dashboard's return math, so chat answers match the
  charts.
- Demo mode (`--demo`) answers over synthetic data and still needs a key.

- [ ] **Step 3: Run the full project test suite**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: PASS (existing tests + new chat tests; no regressions)

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
Document the chat intelligence layer in the README

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01YS52WDc9yuBZurvjF9T55c
EOF
)"
```

---

## Self-Review Notes (for the implementer)

- **Single source of return math:** every tool routes through `DASH_HANDLER` /
  `libraries/returns.py`. Don't reimplement return formulas in `tools.py`.
- **Dispatcher never raises:** all tool errors become strings the model sees.
- **Persisted history is plain text only** (JSON-serializable for `dcc.Store`);
  tool-call content lives only inside a single `engine.run`.
- **View-context Store is a seam:** it exists and is read now, but no other tab
  writes to it yet — that's deferred to the causal phase, by design.
- **If the real `DashboardHandler` dimension/summary column names differ** from the
  fakes, trust the real handler (verified against `DashboardHandler.py`) and adjust
  the fake, not the tool.

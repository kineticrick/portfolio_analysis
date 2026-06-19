# Portfolio Chat Intelligence Layer — Design

**Date:** 2026-06-19
**Status:** Approved (pending implementation plan)

## Overview

Add a natural-language chat interface to the portfolio analysis dashboard so the
user can ask questions about their portfolio, holdings, dimensions, and history in
plain English — e.g. *"What are the top 5 performing assets in my discretionary
account over the last 6 months?"* — and get back both a prose answer and, where
useful, a chart generated on the fly.

The first version targets **structured retrieval** (deterministic data Q&A:
rankings, filters, returns over intervals, comparisons). Causal/explanatory
reasoning (*"why did the retirement account jump in late May?"*) is explicitly
**deferred to a later phase**, but the architecture leaves clean seams for it.

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Scope (v1)** | Retrieval first; causal "why" deferred | Deterministic Q&A is reliable, ships fast, and is the foundation the causal phase builds on. |
| **Model host** | Claude API, default **Sonnet 4.6**, behind a provider interface; Haiku 4.5 a config-swap fallback | Sonnet gives reliability headroom (compositional queries, good refusal behavior) for financial data; cost at personal scale is a few $/mo. The provider seam keeps a local model (Ollama) one class away. |
| **Interface** | New **"Chat" tab** + top-level shared `dcc.Store` for Level-1 view awareness; inline dynamic charts | ~90% of the awareness value with far less plumbing than a per-page side panel. Charts render naturally inside a Dash callback. |
| **Data access** | **Tool-calling** over the existing tested `DashboardHandler` API + chart-builders | The correct return math (value-weighting, rebasing, split/acquisition handling) lives in Python, not SQL. Tool-calling reuses it, so chat answers and dashboard charts agree by construction. Text-to-SQL would bypass it and produce plausible-but-wrong numbers. |

## Architecture

Four units with one-way dependencies: **UI → engine → (provider, tools) → DASH_HANDLER**.

### 1. Provider layer — `libraries/chat/provider.py`

A thin `LLMProvider` interface with one concrete `AnthropicProvider`. Responsible
*only* for LLM I/O: send messages + tool schemas, return either tool-call requests
or a final text answer. This is the "local-ready" seam — adding Ollama later means
writing one more class; nothing else changes.

### 2. Tool layer — `libraries/chat/tools.py` + `libraries/chat/chart_builders.py`

- `tools.py` — tool *schemas* (what the model sees) and a **dispatcher** mapping a
  tool call to the corresponding `DASH_HANDLER` method. Pure data access; no LLM
  knowledge. Each dispatch is wrapped in try/except and returns an error string to
  the model on failure, so the model can recover or ask to clarify.
- `chart_builders.py` — reusable plotly figure builders factored from the patterns
  already in the tab files, reusing `libraries/returns.py` for rebasing.

### 3. Chat engine — `libraries/chat/engine.py`

Orchestrates the tool-calling loop: take the conversation + new question → provider
→ if the model requests a tool, dispatch it → feed the result back → repeat until
the model returns prose. Output: `(answer_text, [figures])`. Knows nothing about
Dash. Takes `DASH_HANDLER` **by reference**, so it works automatically in demo mode
(tools hit `DemoDashboardHandler`). A **max tool-iteration cap** (e.g. 5) prevents
runaway loops.

### 4. Dash UI — `visualization/dash/portfolio_dashboard/tabs/chat_tab.py`

The Chat tab: input box + Send button, a scrollable thread that renders text
bubbles and inline `dcc.Graph`s, and the callback wiring input → engine. Non-
streaming for v1 (input disabled + spinner while running).

### File layout

```
libraries/chat/
  __init__.py
  provider.py        # LLMProvider, AnthropicProvider
  tools.py           # tool schemas + dispatcher
  chart_builders.py  # reusable plotly figure builders
  engine.py          # tool-calling loop, returns (text, figures)
  config.py          # model name, system prompt, tool registry, limits
visualization/dash/portfolio_dashboard/tabs/chat_tab.py
tests/libraries/chat/test_tools.py
tests/libraries/chat/test_engine.py
tests/libraries/chat/test_chart_builders.py
```

## Tool Set (v1)

Kept tight (~7 tools) — tool-selection reliability drops as the list grows. Add
more based on real gaps.

**Data tools** (return structured results for the model to narrate):

1. **`rank_assets`** — top/bottom N performers. Args: `interval`, `count`,
   `metric` (price-return | value), `ascending`, optional `filters`
   (sector / asset_type / account_type / geography). Wraps `get_ranked_assets` +
   summary filtering.
2. **`get_portfolio_summary`** — total value, cost basis, return over an interval,
   plus milestone returns. Wraps `get_portfolio_milestones` + current value.
3. **`get_asset_detail`** — one ticker: current value/price, cost basis, return
   over an interval, dividend yield, holding account type(s). From
   `current_portfolio_summary_df` + `get_asset_milestones`.
4. **`get_dimension_breakdown`** — value-weighted return and dollar value by a
   dimension (sectors / asset_types / account_types / geography) over an interval.
   From the dimension summary/history DataFrames.
5. **`filter_holdings`** — list holdings matching filters, returning chosen
   columns. Query over `current_portfolio_summary_df`.

**Chart tools** (compute *and* render — return a compact text summary to the model
**and** a figure to the UI):

6. **`show_history_line`** — rebased % line chart for one or more targets:
   asset(s), a dimension's members, or the whole portfolio, over an interval.
   Reuses `chart_builders` + `libraries/returns.py`.
7. **`show_ranked_bar`** — bar chart of top/bottom N performers (visual counterpart
   to `rank_assets`).

### Trustworthiness guarantees

- **Single source of return math.** Every tool routes through the same
  `DASH_HANDLER` methods and `libraries/returns.py` the dashboard already uses, so
  a chat number equals the corresponding dashboard number by construction.
- **Fixed enums.** Interval (`1w, 1m, 3m, 6m, 1y, 2y, 3y, 5y, Lifetime`) and
  dimension (`Sector, AssetType, AccountType, Geography`) vocabularies are encoded
  in the tool schemas, eliminating a class of hallucinated-argument errors.

A chart tool's dispatch returns *both* a small text summary (so the model can
describe what it drew) and a figure object the engine collects for the UI to render
inline — yielding prose **and** chart in one answer.

## Conversation State (Dash)

Three top-level `dcc.Store`s:

- **`chat-history-store`** — the running LLM message list (multi-turn context),
  trimmed to a max number of turns to bound tokens/cost.
- **`chat-thread-store`** — the rendered conversation (per entry: role, text,
  optional serialized figure) so the thread survives re-renders.
- **`view-context-store`** — the Level-1 awareness blob (`{dimension, interval}`),
  wired as a `State` into the callback now; other tabs populate it later. Empty is
  acceptable for v1.

**On Send:** append user message → `engine.run(history, user_msg, view_context,
DASH_HANDLER)` → `(answer_text, [figures])` → append assistant bubble + inline
graphs → update both stores → re-render thread.

## Error Handling

The callback must never crash:

- **API errors** (auth / rate-limit / network) — caught in the engine, surfaced as
  a friendly assistant bubble.
- **Tool errors** (bad args, empty result) — dispatcher returns an error string to
  the model so it can recover or ask to clarify.
- **Missing API key** — the tab shows a clear setup message instead of erroring.

## Configuration

`config.py` + environment:

- `ANTHROPIC_API_KEY` from env (never logged).
- Model = Sonnet 4.6; `MAX_TOKENS`; max tool-iterations; conversation-trim length;
  the tool registry; the **system prompt** stating the assistant's role, available
  data, fixed vocab, and the rule *"use tools; never guess numbers; say when you
  can't answer."*

## Demo Mode

Because the engine takes `DASH_HANDLER` by reference, in `--demo` the tools
automatically hit `DemoDashboardHandler` and chat answers over synthetic data with
no extra work. It still needs an API key to call Claude; without one, the same
setup message shows. No canned demo responses for v1.

## Security

Read-only by construction: the dispatcher only calls whitelisted handler methods;
chat never writes to the DB or executes arbitrary code. The API key is read from
the environment and never logged.

## Testing

No live API calls:

- **`test_tools.py`** — each tool dispatches to the right handler method with
  correct args and output shape; uses `DemoDashboardHandler` as a deterministic,
  DB-free stand-in.
- **`test_chart_builders.py`** — builders return valid plotly figures with the
  expected traces from sample DataFrames.
- **`test_engine.py`** — a **mock provider** scripts "tool call → final answer" to
  exercise the loop offline: dispatch, figure collection, history accumulation, the
  iteration cap, and error paths.

## Deferred / Future Phases

- **Causal reasoning** ("why did X move") — needs event/attribution data and richer
  context; pairs naturally with deeper view-awareness. Likely upgrades the default
  model to Sonnet/Opus per-query.
- **Level-2 view awareness** (selected rows, hovered points) — wait for the causal
  phase that needs it.
- **Streaming responses** — deferred for v1 (Dash complexity).
- **Hybrid query escape hatch** (constrained pandas `query` tool) — add if real
  usage reveals gaps the fixed tool set can't cover.
- **Local model** (Ollama) — add a second `LLMProvider`; possibly route easy
  queries to Haiku and hard ones to Sonnet for cost optimization.

"""Static configuration for the chat layer."""

from pathlib import Path

from dotenv import load_dotenv

# Load a local .env file (repo root) so secrets like ANTHROPIC_API_KEY can live
# in a file instead of being exported in every shell. This does NOT override
# variables already set in the real environment, and is a no-op if no .env exists.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

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
tool so a figure is rendered. Default to the line chart (show_history_line): even \
for "top N" or ranking requests, plot each asset's history over the interval so the \
trends are visible over time. Only use the bar chart (show_ranked_bar) when the user \
explicitly asks for a bar chart.
- Keep prose answers concise and reference the concrete numbers the tools return.
"""

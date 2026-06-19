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
    return_col = "Price % Return" if metric == "price" else "Value % Return"
    cols = ["Symbol", "Interval", "Current Price", return_col]
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
    cost = rows["Cost Basis"].sum()
    lifetime_return = (value - cost) / cost * 100
    lines = [f"{symbol} ({rows['Name'].iloc[0]}) — held in {accounts}.",
             f"Current price ${price:,.2f}, total value ${value:,.2f}.",
             f"Lifetime return {lifetime_return:.2f}%."]
    if interval != "Lifetime":
        ms = handler.get_asset_milestones(symbols=[symbol])
        m = ms[ms["Interval"] == interval]
        if not m.empty:
            lines.append(f"{interval} price return "
                         f"{m['Price % Return'].iloc[0]:.2f}%.")
    return "\n".join(lines), None


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


# ---- dispatcher ---------------------------------------------------------------

_TOOLS = {
    "rank_assets": rank_assets,
    "get_portfolio_summary": get_portfolio_summary,
    "get_asset_detail": get_asset_detail,
    "get_dimension_breakdown": get_dimension_breakdown,
    "filter_holdings": filter_holdings,
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

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

"""Pure return-math helpers shared by the history chart callbacks.

No DB or Dash imports — keep this unit-testable in isolation.
"""
import pandas as pd


def value_weighted_lifetime_return(total_value: pd.Series,
                                   total_cost_basis: pd.Series) -> pd.Series:
    """Return-on-cost-basis for an aggregate, as a percent.

    Value-weighted because the inputs are summed dollars, not averaged ratios.
    """
    return (total_value - total_cost_basis) / total_cost_basis * 100


def rebase_to_window_start(values: pd.Series) -> pd.Series:
    """Multiplicative rebase of a value/price series to its first element.

    window_return(t) = values(t) / values(t0) - 1, expressed as a percent.
    The first element is therefore always 0%.
    """
    base = values.iloc[0]
    return (values / base - 1) * 100

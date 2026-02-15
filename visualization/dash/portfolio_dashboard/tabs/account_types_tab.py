from visualization.dash.portfolio_dashboard.tabs.dimension_tab_factory import create_dimension_tab

account_types_tab = create_dimension_tab(
    dimension_name="account_types",
    column_name="AccountType",
    summary_df_attr="account_types_summary_df",
    history_df_attr="account_types_history_df",
)

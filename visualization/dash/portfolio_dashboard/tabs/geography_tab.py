from visualization.dash.portfolio_dashboard.tabs.dimension_tab_factory import create_dimension_tab

geography_tab = create_dimension_tab(
    dimension_name="geography",
    column_name="Geography",
    summary_df_attr="geography_summary_df",
    history_df_attr="geography_history_df",
)

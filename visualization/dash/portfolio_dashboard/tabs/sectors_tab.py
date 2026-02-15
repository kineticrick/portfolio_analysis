from visualization.dash.portfolio_dashboard.tabs.dimension_tab_factory import create_dimension_tab

sectors_tab = create_dimension_tab(
    dimension_name="sectors",
    column_name="Sector",
    summary_df_attr="sectors_summary_df",
    history_df_attr="sectors_history_df",
)

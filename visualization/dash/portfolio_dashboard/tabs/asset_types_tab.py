from visualization.dash.portfolio_dashboard.tabs.dimension_tab_factory import create_dimension_tab

asset_types_tab = create_dimension_tab(
    dimension_name="asset_types",
    column_name="AssetType",
    summary_df_attr="asset_types_summary_df",
    history_df_attr="asset_types_history_df",
    tab_id="asset-types-dash-tab",
)

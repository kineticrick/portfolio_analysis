from dash import Dash, dcc, html, Input, Output, callback
import plotly.express as px

import pandas as pd
import numpy as np

import os 
import sys 
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from libraries.pandas_helpers import print_full
from libraries.vars import BUSINESS_CADENCE_MAP

csv_file = "./daily_asset_values.csv"

daily_values_df = pd.read_csv('daily_asset_values.csv')

asset_values_df = daily_values_df[daily_values_df['Date'] == '2023-06-14']
asset_values_df = asset_values_df.sort_values(by=['Symbol'], ascending=True)
asset_values_df = asset_values_df.reset_index(drop=True)
print_full(asset_values_df)

# global_daily_values_df = daily_values_df.groupby('Date')['Value'].sum()

# global_daily_values_df = global_daily_values_df.reset_index()
# global_daily_values_df['Date'] = pd.to_datetime(global_daily_values_df['Date'])

# date_range = pd.date_range(start=global_daily_values_df['Date'].min(), 
#                    end=global_daily_values_df['Date'].max(), 
#                    freq='180D')

# numdate = [x for x in range(len(date_range))]
# marks = {numd:date.date() 
#          for numd,date in zip(numdate, date_range)}

# app = Dash(__name__)

# app.layout = html.Div([
#     dcc.Graph(id='historical-value-graph'),
#     dcc.Slider(
#         min=numdate[0],
#         max=numdate[-1],
#         value=numdate[0],
#         marks=marks,
#         id='date-slider'
#     )
# ])

# @callback(
#     Output('historical-value-graph', 'figure'),
#     Input('date-slider', 'value'))
# def update_figure(selected_date_value):
#     selected_date = np.datetime64(marks[selected_date_value])
#     filtered_df = global_daily_values_df[global_daily_values_df['Date'] >= selected_date]
#     print(filtered_df)
#     fig = px.line(filtered_df, 
#                   x=filtered_df['Date'], 
#                   y=filtered_df['Value'],
#                   ) 
    
#     fig.update_layout(transition_duration=500)

#     return fig

# if __name__ == '__main__':
#     app.run_server(debug=True)

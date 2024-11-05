import unittest
import pandas as pd
from datetime import datetime
from libraries.helpers import gen_hist_quantities, gen_assets_historical_value, gen_aggregated_historical_value

class TestHelpers(unittest.TestCase):
    def setUp(self):
        # Create sample test data
        self.test_data = pd.DataFrame({
            'Date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'Symbol': ['AAPL', 'AAPL', 'AAPL'],
            'Action': ['buy', 'buy', 'sell'],
            'Quantity': [100, 50, 75],
            'PricePerShare': [150.0, 155.0, 160.0],
            'Multiplier': [1, 1, 1]
        })

    def test_gen_hist_quantities_basic(self):
        result = gen_hist_quantities(self.test_data)
        
        # Verify final quantity is correct (100 + 50 - 75 = 75)
        self.assertEqual(result.iloc[-1]['Quantity'], 75)
        
        # Verify cost basis calculation
        expected_cost_basis = (100 * 150.0) + (50 * 155.0) - (75 * 150.0)
        self.assertAlmostEqual(result.iloc[-1]['CostBasis'], expected_cost_basis)

    def test_gen_hist_quantities_split(self):
        # Add a 2:1 split to test data
        split_data = self.test_data.copy()
        split_data.loc[len(split_data)] = {
            'Date': '2024-01-04',
            'Symbol': 'AAPL',
            'Action': 'split',
            'Quantity': 0,
            'PricePerShare': 0,
            'Multiplier': 2
        }
        
        result = gen_hist_quantities(split_data)
        
        # Verify quantity doubles after split (75 * 2 = 150)
        self.assertEqual(result.iloc[-1]['Quantity'], 150)
        
        # Verify cost basis remains the same after split
        pre_split_cost_basis = result.iloc[-2]['CostBasis']
        post_split_cost_basis = result.iloc[-1]['CostBasis']
        self.assertAlmostEqual(pre_split_cost_basis, post_split_cost_basis)

    def test_gen_hist_quantities_acquisition(self):
        # Test acquisition scenario
        acquisition_data = pd.DataFrame({
            'Date': ['2024-01-01', '2024-01-02'],
            'Symbol': ['TARGET', 'TARGET'],
            'Action': ['buy', 'acquisition-target'],
            'Quantity': [100, 0],
            'PricePerShare': [50.0, 0],
            'Multiplier': [1, 0]
        })
        
        result = gen_hist_quantities(acquisition_data)
        
        # Verify quantity goes to 0 after acquisition
        self.assertEqual(result.iloc[-1]['Quantity'], 0)

    def test_gen_assets_historical_value(self):
        symbols = ['AAPL']
        
        # Test basic value calculation
        result = gen_assets_historical_value(symbols)
        self.assertTrue(all(col in result.columns for col in 
                           ['Date', 'Symbol', 'Quantity', 'CostBasis', 
                            'ClosingPrice', 'Value', 'PercentReturn']))
        
        # Test with start date
        start_date = '2024-01-01'
        dated_result = gen_assets_historical_value(symbols, start_date=start_date)
        self.assertTrue(all(date >= pd.Timestamp(start_date) 
                           for date in dated_result['Date']))
        
        # Test different cadences
        weekly_result = gen_assets_historical_value(symbols, cadence='weekly')
        monthly_result = gen_assets_historical_value(symbols, cadence='monthly')
        self.assertTrue(len(weekly_result) < len(result))  # Should have fewer rows
        self.assertTrue(len(monthly_result) < len(weekly_result))

    def test_gen_aggregated_historical_value(self):
        symbols = ['AAPL']
        # Test sector aggregation
        sector_result = gen_aggregated_historical_value('Sector', symbols=symbols)
        self.assertTrue('Sector' in sector_result.columns)
        self.assertTrue('AvgPercentReturn' in sector_result.columns)
        
        # Test asset type aggregation
        asset_type_result = gen_aggregated_historical_value('Asset Type', symbols=symbols)
        self.assertTrue('Asset Type' in asset_type_result.columns)
        
        # Test with specific symbols
        # symbols = ['AAPL', 'MSFT']
        # filtered_result = gen_aggregated_historical_value('Sector', symbols=symbols)
        # print(filtered_result)
        # self.assertTrue(all(row['Symbol'] in symbols 
        #                    for _, row in filtered_result.iterrows()))

if __name__ == '__main__':
    unittest.main() 
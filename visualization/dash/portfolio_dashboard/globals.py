from visualization.dash.DashboardHandler import DashboardHandler

DASH_HANDLER = DashboardHandler()

MILESTONES = DASH_HANDLER.portfolio_milestones
INTERVALS = MILESTONES['Interval'].values.tolist()

CURRENT_PORTFOLIO_VALUE = DASH_HANDLER.current_portfolio_value

DEFAULT_INTERVAL = 'Lifetime'

### PORTFOLIO TAB ###
NUM_WINNERS_LOSERS = 5
PORTFOLIO_DEFAULT_INTERVAL = '1d'
PORTFOLIO_MILESTONES = MILESTONES[['Interval', 'Value', 'Value % Return']]
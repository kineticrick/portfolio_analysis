import yfinance as yf

def get_info(tickers): 
    assert(isinstance(tickers, list))
    
    ticker_str = " ".join(tickers)
    
    ticker_info = {} 
    if len(tickers) == 1: 
        ticker = yf.Ticker(ticker_str)
        symbol = ticker.info['symbol']
        ticker_info[symbol] = ticker.info
    elif len(tickers) > 1: 
        tickers = yf.Tickers(ticker_str)
        for obj in tickers.tickers: 
            symbol = obj.info['symbol']
            ticker_info[symbol] = obj.info
    
    return ticker_info

def get_dividend_yield(tickers): 
    div_yields = {}
    for symbol, info in get_info(tickers).items(): 
        div_yields[symbol] = info['dividendYield']
    
    return div_yields

def show_all_avail_keys(): 
    info = get_info(["aapl"])   
    data = info['AAPL']
    sorted_pairs = sorted(data.items())
    for k, v in sorted_pairs: 
        print(k, v)
    
    
    
    
    
    # return info.keys()
    

    
    

# tickers = ['LDOS', 'V', 'PEP', 'STZ', 'KO', 'EQIX', 'MS', 'MGP', 'ASML', 
#            'KBH', 'HD', 'DRE', 'PHM', 'PEAK', 'MA']
# # print(get_dividend_yield(tickers))

# print(show_all_avail_keys())

msft = yf.Ticker("AAPL")

hist = msft.history()

print(msft.balance_sheet)
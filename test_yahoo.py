import yfinance as yf

tickers = ["MAYBANK.KL", "1155.KL", "PBBANK.KL", "1295.KL"]
for t in tickers:
    try:
        stock = yf.Ticker(t)
        info = stock.info
        print(f"{t}: {info.get('shortName', 'N/A')}")
    except Exception as e:
        print(f"{t}: Error - {e}")

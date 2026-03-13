import yfinance as yf

symbols = ["MAYBANK.KL", "PBBANK.KL", "CIMB.KL", "TENAGA.KL", "99SMART.KL", "KOSSAN.KL"]
for s in symbols:
    try:
        stock = yf.Ticker(s)
        info = stock.info
        print(f"{s}: {info.get('shortName', 'N/A')}")
    except Exception as e:
        print(f"{s}: Error - {e}")

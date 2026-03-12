
import yfinance as yf
import pandas as pd

def inspect_columns(ticker_symbol):
    print(f"Inspecting columns for {ticker_symbol}...")
    try:
        stock = yf.Ticker(ticker_symbol)
        bs = stock.balance_sheet
        print("\n--- Balance Sheet Rows ---")
        for idx in bs.index:
            print(idx)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_columns("5296.KL")

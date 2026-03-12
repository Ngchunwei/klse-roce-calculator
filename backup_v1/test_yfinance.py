
import yfinance as yf
import pandas as pd

def get_financials(ticker_symbol):
    print(f"Fetching data for {ticker_symbol}...")
    try:
        stock = yf.Ticker(ticker_symbol)
        
        # 获取年度财务报表
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        
        if financials.empty or balance_sheet.empty:
            print("No data found.")
            return

        print("\n--- Financials Columns ---")
        print(financials.columns)
        print("\n--- Balance Sheet Columns ---")
        print(balance_sheet.columns)
        
        # 尝试获取关键字段
        # Yahoo Finance 字段名可能有所不同，通常是 'EBIT', 'Total Assets', 'Total Current Liabilities'
        
        # 打印一些关键行以供检查
        print("\n--- Key Rows in Financials ---")
        for row in ['EBIT', 'Operating Income', 'Net Income']:
            if row in financials.index:
                print(f"{row}:\n{financials.loc[row]}")
            else:
                print(f"{row} not found")

        print("\n--- Key Rows in Balance Sheet ---")
        for row in ['Total Assets', 'Total Current Liabilities']:
            if row in balance_sheet.index:
                print(f"{row}:\n{balance_sheet.loc[row]}")
            else:
                print(f"{row} not found")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # 测试 MRDIY
    get_financials("5296.KL")

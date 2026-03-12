from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
import math
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

def clean_value(val):
    if pd.isna(val) or val is None:
        return 0
    return float(val)

def fetch_yahoo(code):
    # Handle KLSE suffix
    ticker_symbol = code
    if not ticker_symbol.endswith('.KL'):
        ticker_symbol = f"{code}.KL"

    print(f"Fetching data from Yahoo for {ticker_symbol}...")
    
    try:
        stock = yf.Ticker(ticker_symbol)
        
        fin = stock.financials
        bs = stock.balance_sheet
        
        if fin.empty or bs.empty:
            return None, f'No data found for {code} on Yahoo Finance'

        def get_row(df, possible_names):
            for name in possible_names:
                if name in df.index:
                    return df.loc[name]
            return None

        ebit_row = get_row(fin, ['EBIT', 'Operating Income'])
        assets_row = get_row(bs, ['Total Assets'])
        cl_row = get_row(bs, ['Current Liabilities', 'Total Current Liabilities'])

        if ebit_row is None or assets_row is None or cl_row is None:
             return None, 'Incomplete financial data on Yahoo Finance'

        years_data = []
        for date in fin.columns:
            year = date.year
            if date in bs.columns:
                try:
                    ebit = clean_value(ebit_row[date])
                    assets = clean_value(assets_row[date])
                    cl = clean_value(cl_row[date])
                    
                    ebit_m = round(ebit / 1_000_000, 1)
                    assets_m = round(assets / 1_000_000, 1)
                    cl_m = round(cl / 1_000_000, 1)
                    
                    years_data.append({
                        'year': year,
                        'ebit': ebit_m,
                        'assets': assets_m,
                        'cl': cl_m
                    })
                except Exception as e:
                    print(f"Error processing year {year}: {e}")
                    continue
        
        years_data.sort(key=lambda x: x['year'], reverse=True)
        return years_data, None

    except Exception as e:
        print(f"Yahoo Error: {e}")
        return None, str(e)

def parse_sa_val(txt):
    if not txt or txt == '-': return 0.0
    # Remove commas
    txt = txt.replace(',', '')
    # Check for percentage (not expected for raw values but just in case)
    if '%' in txt: return 0.0
    try:
        return float(txt)
    except:
        return 0.0

def fetch_stockanalysis(ticker):
    # StockAnalysis requires ticker (e.g. MRDIY), not code (e.g. 5296)
    # If user passed a numeric code, we might fail unless we map it.
    # We will assume user entered Ticker if they chose SA.
    
    print(f"Fetching data from StockAnalysis for {ticker}...")
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}
    
    try:
        # 1. Fetch Income Statement
        url_is = f"https://stockanalysis.com/quote/klse/{ticker}/financials/"
        r_is = requests.get(url_is, headers=headers)
        if r_is.status_code != 200:
            return None, f"Failed to fetch Income Statement from StockAnalysis (Status {r_is.status_code})"
        
        soup_is = BeautifulSoup(r_is.text, 'html.parser')
        table_is = soup_is.find('table')
        if not table_is:
            return None, "No financial table found on StockAnalysis"
            
        # Parse Headers (Years)
        # Headers: Fiscal Year, TTM, 2024, 2023...
        # We need to map column index to Year
        # Note: StockAnalysis usually shows most recent first
        th_cells = [th.text.strip() for th in table_is.find_all('th')]
        
        # Map index to year
        # Skip first column (Fiscal Year)
        col_map = {}
        for i, h in enumerate(th_cells):
            if i == 0: continue
            if 'TTM' in h: continue # Skip TTM for now, or treat as current year? Let's skip to be safe/consistent with annual
            # Extract year from "Dec '24 2024" or just "2024"
            # Usually format is "Dec 31, 2024" inside a small span or just the text
            # The header text might be complex.
            # My previous print showed: "Dec '24 Dec 31, 2024"
            # Let's look for 4 digits
            yr_match = re.search(r'20\d{2}', h)
            if yr_match:
                col_map[i] = int(yr_match.group(0))
        
        # Find Operating Income
        ebit_data = {}
        rows_is = table_is.find_all('tr')
        for row in rows_is:
            cols = [td.text.strip() for td in row.find_all('td')]
            if not cols: continue
            label = cols[0]
            if 'Operating Income' in label or 'EBIT' in label:
                # Extract data for mapped columns
                for idx, year in col_map.items():
                    # idx in cols is same?
                    # The table body td count should match th count?
                    # Usually yes.
                    if idx < len(cols):
                        ebit_data[year] = parse_sa_val(cols[idx])
                break
        
        if not ebit_data:
            return None, "Operating Income not found in StockAnalysis"

        # 2. Fetch Balance Sheet
        url_bs = f"https://stockanalysis.com/quote/klse/{ticker}/financials/balance-sheet/"
        r_bs = requests.get(url_bs, headers=headers)
        if r_bs.status_code != 200:
            return None, "Failed to fetch Balance Sheet from StockAnalysis"
            
        soup_bs = BeautifulSoup(r_bs.text, 'html.parser')
        table_bs = soup_bs.find('table')
        if not table_bs:
            return None, "No balance sheet table found"
            
        # Parse Headers for BS (might differ slightly in availability)
        th_cells_bs = [th.text.strip() for th in table_bs.find_all('th')]
        col_map_bs = {}
        for i, h in enumerate(th_cells_bs):
            if i == 0: continue
            if 'TTM' in h: continue
            yr_match = re.search(r'20\d{2}', h)
            if yr_match:
                col_map_bs[i] = int(yr_match.group(0))
                
        assets_data = {}
        cl_data = {}
        
        rows_bs = table_bs.find_all('tr')
        for row in rows_bs:
            cols = [td.text.strip() for td in row.find_all('td')]
            if not cols: continue
            label = cols[0]
            
            if 'Total Assets' in label:
                for idx, year in col_map_bs.items():
                    if idx < len(cols):
                        assets_data[year] = parse_sa_val(cols[idx])
                        
            # "Total Current Liabilities" or "Current Liabilities"
            if 'Total Current Liabilities' in label or 'Current Liabilities' in label:
                # Sometimes there are multiple matches, prefer Total
                # Usually "Total Current Liabilities" is the sum line
                for idx, year in col_map_bs.items():
                    if idx < len(cols):
                        cl_data[year] = parse_sa_val(cols[idx])

        # Merge Data
        years_data = []
        # Use years found in EBIT as base
        for year, ebit in ebit_data.items():
            if year in assets_data and year in cl_data:
                # StockAnalysis data is usually in Millions already?
                # Let's check my print output: Revenue 4,847.
                # MRDIY revenue is ~4B.
                # If it says 4,847, and if that's Millions, it's 4.8B. Correct.
                # So the values are ALREADY in Millions.
                # My Yahoo code divides by 1,000,000.
                # If StockAnalysis is already in Millions, I should NOT divide, or check scale.
                # Usually StockAnalysis headers say "Currency in MYR" but doesn't explicitly say "Millions" in the cell value.
                # Wait, if Revenue is 4,847, that is 4,847 Millions = 4.8 Billion.
                # So yes, it's in Millions.
                # So I keep as is.
                
                years_data.append({
                    'year': year,
                    'ebit': ebit,
                    'assets': assets_data[year],
                    'cl': cl_data[year]
                })
        
        years_data.sort(key=lambda x: x['year'], reverse=True)
        return years_data, None

    except Exception as e:
        print(f"StockAnalysis Error: {e}")
        return None, str(e)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/roce')
def get_roce_data():
    code = request.args.get('code', '').strip().upper()
    source = request.args.get('source', 'yahoo').strip().lower()
    
    if not code:
        return jsonify({'error': 'No code provided'}), 400

    data = None
    error = None

    if source == 'stockanalysis':
        data, error = fetch_stockanalysis(code)
    else:
        # Default to Yahoo
        data, error = fetch_yahoo(code)
        
    if error:
        return jsonify({'error': error}), 404 if 'No data' in error else 500
        
    return jsonify({'data': data})

if __name__ == '__main__':
    app.run(debug=True, port=5001)

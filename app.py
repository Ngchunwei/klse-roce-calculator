from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
import math
import requests
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor
from klse_tickers import TICKERS
import os
# Try to import PIL and pytesseract
Image = None
pytesseract = None
try:
    from PIL import Image
    import pytesseract
except ImportError:
    pass

app = Flask(__name__)

def clean_value(val):
    if pd.isna(val) or val is None:
        return 0
    return float(val)

import time
import random

# Simple in-memory cache to improve stability and speed during a session
# Format: {ticker: (data, info, timestamp)}
DATA_CACHE = {}
CACHE_EXPIRY = 86400 # 24 hours for better stability across sessions

def fetch_yahoo(code, retries=3):
    # Handle KLSE suffix
    ticker_symbol = code
    if not ticker_symbol.endswith('.KL'):
        ticker_symbol = f"{code}.KL"

    # Check cache
    now = time.time()
    if ticker_symbol in DATA_CACHE:
        cache_data, cache_info, timestamp = DATA_CACHE[ticker_symbol]
        if now - timestamp < CACHE_EXPIRY:
            print(f"Using cached data for {ticker_symbol}")
            return cache_data, cache_info, None

    attempt = 0
    while attempt <= retries:
        print(f"Fetching data from Yahoo for {ticker_symbol} (Attempt {attempt+1})...")
        try:
            stock = yf.Ticker(ticker_symbol)
            
            # Try multiple methods to get financials
            fin = stock.financials
            if fin.empty:
                print(f"Standard financials empty for {ticker_symbol}, trying income_stmt...")
                fin = stock.income_stmt
                
            bs = stock.balance_sheet
            if bs.empty:
                print(f"Standard balance sheet empty for {ticker_symbol}, trying balance_sheet...")
                # Note: stock.balance_sheet is the same as stock.balancesheet
                # but sometimes yfinance has internal issues
                pass
            
            if fin.empty or bs.empty:
                if attempt < retries:
                    wait_time = (attempt + 1) * 3 # Increased wait time
                    print(f"Empty data for {ticker_symbol}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    attempt += 1
                    continue
                return None, None, f'No data found for {code} on Yahoo Finance'

            # Try to get company name
            name = code
            try:
                # Use fast_info if info is slow/failing
                info = stock.info
                name = info.get('shortName') or info.get('longName') or code
            except:
                try:
                    name = stock.fast_info.get('commonName') or code
                except:
                    pass

            def get_row(df, possible_names):
                # Case-insensitive search for row names
                available_rows = [str(i).lower() for i in df.index]
                for name_opt in possible_names:
                    try:
                        idx = available_rows.index(name_opt.lower())
                        return df.iloc[idx]
                    except ValueError:
                        continue
                return None

            ebit_row = get_row(fin, ['EBIT', 'Operating Income', 'OperatingIncome'])
            assets_row = get_row(bs, ['Total Assets', 'TotalAssets'])
            cl_row = get_row(bs, ['Current Liabilities', 'Total Current Liabilities', 'TotalCurrentLiabilities'])

            if ebit_row is None or assets_row is None or cl_row is None:
                 return None, None, 'Incomplete financial data on Yahoo Finance'

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
                        print(f"Error processing year {year} for {ticker_symbol}: {e}")
                        continue
            
            years_data.sort(key=lambda x: x['year'], reverse=True)
            
            # Store in cache before returning
            DATA_CACHE[ticker_symbol] = (years_data, {'name': name}, now)
            return years_data, {'name': name}, None

        except Exception as e:
            print(f"Yahoo Error for {ticker_symbol}: {e}")
            if attempt < retries:
                wait_time = (attempt + 1) * 2
                time.sleep(wait_time)
                attempt += 1
                continue
            return None, None, str(e)
    
    return None, None, "Failed after retries"

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
            return None, None, f"Failed to fetch Income Statement from StockAnalysis (Status {r_is.status_code})"
        
        soup_is = BeautifulSoup(r_is.text, 'html.parser')
        
        # Try to get name
        name = ticker
        h1 = soup_is.find('h1')
        if h1:
            name = h1.text.replace('Income Statement', '').strip()

        table_is = soup_is.find('table')
        if not table_is:
            return None, None, "No financial table found on StockAnalysis"
            
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
            return None, None, "Operating Income not found in StockAnalysis"

        # 2. Fetch Balance Sheet
        url_bs = f"https://stockanalysis.com/quote/klse/{ticker}/financials/balance-sheet/"
        r_bs = requests.get(url_bs, headers=headers)
        if r_bs.status_code != 200:
            return None, None, "Failed to fetch Balance Sheet from StockAnalysis"
            
        soup_bs = BeautifulSoup(r_bs.text, 'html.parser')
        table_bs = soup_bs.find('table')
        if not table_bs:
            return None, None, "No balance sheet table found"
            
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
                
                years_data.append({
                    'year': year,
                    'ebit': ebit,
                    'assets': assets_data[year],
                    'cl': cl_data[year]
                })
        
        years_data.sort(key=lambda x: x['year'], reverse=True)
        return years_data, {'name': name}, None
        
    except Exception as e:
        print(f"StockAnalysis Error: {e}")
        return None, None, str(e)

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
    info = None
    error = None

    if source == 'stockanalysis':
        data, info, error = fetch_stockanalysis(code)
    else:
        data, info, error = fetch_yahoo(code)
        
    if error:
        return jsonify({'error': error}), 404 if 'No data' in error else 500
        
    return jsonify({'data': data, 'info': info})

@app.route('/api/scan')
def scan_stocks():
    try:
        min_roce = float(request.args.get('min_roce', 20.0))
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 50))
        deep_scan = request.args.get('deep_scan', 'false').lower() == 'true'
        
        # Get the current batch of tickers
        current_tickers = TICKERS[offset : offset + limit]
        
        if not current_tickers:
            return jsonify({
                'results': [], 
                'finished': True, 
                'total_tickers': len(TICKERS),
                'offset': offset
            })

        print(f"Scanning batch: {offset} to {offset + len(current_tickers)} (Deep Scan: {deep_scan})")
        
        results = []
        
        def check_stock(ticker):
            try:
                # Add a small random delay to avoid rate limiting
                import time
                import random
                time.sleep(random.uniform(0.1, 0.5))
                
                data, info, err = fetch_yahoo(ticker)
                
                if not data or err:
                    return

                if not info:
                    info = {'name': ticker.replace('.KL', '')}
                
                # data is sorted by year desc
                latest = data[0]
                
                def calculate_roce(year_entry):
                    try:
                        ebit = year_entry.get('ebit', 0)
                        assets = year_entry.get('assets', 0)
                        cl = year_entry.get('cl', 0)
                        capital_employed = assets - cl
                        if capital_employed <= 0:
                            return None
                        return (ebit / capital_employed) * 100
                    except:
                        return None

                latest_roce = calculate_roce(latest)
                if latest_roce is None:
                    return

                roce_history = []
                passed_deep_scan = True
                
                # Check history
                check_years = 4 if deep_scan else min(len(data), 4)
                
                all_roces = []
                if deep_scan and len(data) < 4:
                    passed_deep_scan = False
                else:
                    for i in range(check_years):
                        if i >= len(data):
                            if deep_scan: passed_deep_scan = False
                            break
                        roce = calculate_roce(data[i])
                        if roce is not None:
                            all_roces.append(roce)
                            if deep_scan and roce < min_roce:
                                passed_deep_scan = False
                        else:
                            if deep_scan: passed_deep_scan = False
                        
                        roce_history.append({
                            'year': data[i]['year'],
                            'roce': round(roce, 1) if roce is not None else None
                        })
                
                if deep_scan and not passed_deep_scan:
                    return
                
                if not deep_scan and latest_roce < min_roce:
                    return

                # Calculate average ROCE
                avg_roce = sum(all_roces) / len(all_roces) if all_roces else 0

                results.append({
                    'code': ticker.replace('.KL', ''),
                    'name': info.get('name', ticker),
                    'roce': round(latest_roce, 1),
                    'avg_roce': round(avg_roce, 1),
                    'year': latest['year'],
                    'history': roce_history
                })
            except Exception as e:
                print(f"Error checking {ticker}: {e}")

        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(check_stock, current_tickers)
            
        results.sort(key=lambda x: x['roce'], reverse=True)
        
        return jsonify({
            'results': results,
            'offset': offset,
            'limit': limit,
            'total_tickers': len(TICKERS),
            'finished': (offset + len(current_tickers)) >= len(TICKERS)
        })
    except Exception as e:
        print(f"Scan Route Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ocr', methods=['POST'])
def ocr_process():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        # Check if tesseract is available
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
        except Exception:
            return jsonify({'error': 'Tesseract OCR is not installed or not found. Please install Tesseract (e.g., `brew install tesseract` on macOS) to use this feature.'}), 500

        if Image is None:
             return jsonify({'error': 'PIL (Pillow) library is not installed.'}), 500
            
        image = Image.open(file.stream)
        
        # Perform OCR
        # We need raw data to find coordinates
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        
        # Simple heuristic to extract table data
        # 1. Find Year Headers (e.g., 2021, 2022, 2023...)
        # 2. Find Row Headers (Revenue, Operating Income, Total Assets...)
        
        years = {} # {year: x_center}
        rows = {}  # {label: y_center}
        
        n_boxes = len(data['text'])
        
        # 1. Find Years
        for i in range(n_boxes):
            text = data['text'][i].strip()
            # Look for 4 digit years starting with 20
            if re.match(r'^20\d{2}$', text):
                x = data['left'][i] + data['width'][i] / 2
                years[int(text)] = x
            # Handle "FY 2021" or "FY2021"
            elif re.match(r'^FY\s?20\d{2}$', text, re.IGNORECASE):
                match = re.search(r'20\d{2}', text)
                if match:
                    yr = int(match.group(0))
                    x = data['left'][i] + data['width'][i] / 2
                    years[yr] = x
                
        if not years:
            return jsonify({'error': 'No years found in the image. Ensure the table has year headers (e.g. 2023).'}), 400
            
        # 2. Find Keywords
        # We look for specific keywords and get their Y coordinates
        keywords = {
            'ebit': ['Operating Income', 'EBIT', 'Operating Profit'],
            'assets': ['Total Assets'],
            'cl': ['Total Current Liabilities', 'Current Liabilities']
        }
        
        found_rows = {} # {type: y_center}
        
        # Helper to find phrase
        def find_phrase(phrase):
            # Split phrase into words
            words = phrase.split()
            # Try to find sequence of words
            for i in range(n_boxes - len(words) + 1):
                match = True
                for j in range(len(words)):
                    if words[j].lower() not in data['text'][i+j].lower():
                        match = False
                        break
                if match:
                    # Found! Use Y of first word
                    return data['top'][i] + data['height'][i] / 2
            return None

        for k, phrases in keywords.items():
            for p in phrases:
                y = find_phrase(p)
                if y:
                    found_rows[k] = y
                    break
        
        if not found_rows:
            return jsonify({'error': 'No financial keywords (Operating Income, Total Assets, etc.) found.'}), 400

        # 3. Extract Values
        extracted_data = []
        
        # Sort years to process
        sorted_years = sorted(years.keys(), reverse=True)
        
        for yr in sorted_years:
            year_x = years[yr]
            entry = {'year': yr}
            
            for k, row_y in found_rows.items():
                # Find number closest to (year_x, row_y)
                best_val = None
                min_dist = float('inf')
                
                for i in range(n_boxes):
                    text = data['text'][i].strip().replace(',', '')
                    if not text: continue
                    
                    # Check if number
                    try:
                        val = float(text)
                    except:
                        continue
                        
                    # Calculate distance
                    # We care mostly about Y alignment with row, and X alignment with year
                    # But rows might be wide.
                    # Usually values are in the same Y-band.
                    
                    box_x = data['left'][i] + data['width'][i] / 2
                    box_y = data['top'][i] + data['height'][i] / 2
                    
                    y_diff = abs(box_y - row_y)
                    x_diff = abs(box_x - year_x)
                    
                    # Thresholds: Y should be very close (same line), X should be relatively close
                    if y_diff < 20 and x_diff < 100: # Pixels, might need tuning
                        dist = x_diff + y_diff * 2 # Penalize Y diff more
                        if dist < min_dist:
                            min_dist = dist
                            best_val = val
                
                if best_val is not None:
                    entry[k] = best_val
            
            if 'ebit' in entry or 'assets' in entry or 'cl' in entry:
                extracted_data.append(entry)
                
        return jsonify({'data': extracted_data})

    except Exception as e:
        print(f"OCR Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Use port from environment variable for deployment compatibility
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, host='0.0.0.0', port=port)

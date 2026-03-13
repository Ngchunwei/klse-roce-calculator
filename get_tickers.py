import requests
import re

def get_tickers():
    url = "https://www.malaysiastock.biz/Stock-List.aspx"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        r = requests.get(url, headers=headers)
        print(f"Status Code: {r.status_code}")
        # Look for the pattern id=xxxx
        codes = re.findall(r'id=(\d{4})', r.text)
        print(f"Found {len(codes)} codes via regex id=(\d{{4}})")
        
        if not codes:
            # Try another pattern: >NAME (1234)<
            codes = re.findall(r'\((\d{4})\)', r.text)
            print(f"Found {len(codes)} codes via regex \((\d{{4}})\)")
            
        return sorted(list(set([f"{c}.KL" for c in codes if c.isdigit()])))
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    t = get_tickers()
    print(f"Total Unique Tickers: {len(t)}")
    if len(t) > 500:
        with open('klse_tickers.py', 'w') as f:
            f.write(f"TICKERS = {t}\n")
        print("Updated klse_tickers.py successfully.")
    else:
        print("Failed to find enough tickers.")

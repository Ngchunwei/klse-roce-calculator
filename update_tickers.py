import requests
import re

def get_from_i3investor():
    print("Fetching from I3investor all stocks...")
    url = "https://klse.i3investor.com/web/stock/list"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        r = requests.get(url, headers=headers)
        # Codes are often like 1234 or in links
        # Let's try to find any 4-digit code that is surrounded by non-digits
        codes = re.findall(r'\b(\d{4})\b', r.text)
        return sorted(list(set([f"{c}.KL" for c in codes if c.isdigit() and len(c) == 4])))
    except:
        return []

if __name__ == "__main__":
    t = get_from_i3investor()
    # Filter out years
    t = [c for c in t if not (c.startswith('20') or c.startswith('19'))]
    print(f"Total Tickers: {len(t)}")
    if len(t) > 100:
        with open('klse_tickers.py', 'w') as f:
            f.write(f"TICKERS = {t}\n")
        print("Success.")

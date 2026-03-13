import requests
from bs4 import BeautifulSoup
import re

def get_klse_tickers():
    print("Fetching all KLSE tickers...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = "https://www.klsescreener.com/v2/stocks"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to fetch stocks list: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # Tickers are usually in a table or list
        # On klsescreener, they are in <td> elements with specific classes or patterns
        tickers = []
        # Find all 4-digit codes
        # The codes on KLSE are 4 digits.
        # Example: 5296 (MRDIY)
        # In the page, they might appear as text or in links
        # Let's look for links that look like /v2/stocks/view/5296
        links = soup.find_all('a', href=re.compile(r'/v2/stocks/view/\d{4}'))
        for link in links:
            code = link['href'].split('/')[-1]
            if code not in tickers:
                tickers.append(f"{code}.KL")
        
        print(f"Found {len(tickers)} tickers.")
        return sorted(tickers)
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    tickers = get_klse_tickers()
    if tickers:
        with open('klse_tickers_all.py', 'w') as f:
            f.write("TICKERS = [\n")
            for t in tickers:
                f.write(f"    '{t}',\n")
            f.write("]\n")
        print(f"Saved {len(tickers)} tickers to klse_tickers_all.py")

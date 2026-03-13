import requests
from bs4 import BeautifulSoup
import re

def get_klse_tickers():
    print("Fetching all KLSE tickers from malaysiastock.biz...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = "https://www.malaysiastock.biz/Stock-List.aspx"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to fetch stocks list: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # Tickers are in <a> tags with href containing 'Stock-Quote.aspx?id='
        links = soup.find_all('a', href=re.compile(r'Stock-Quote\.aspx\?id=\d{4}'))
        tickers = []
        for link in links:
            match = re.search(r'id=(\d{4})', link['href'])
            if match:
                code = match.group(1)
                if f"{code}.KL" not in tickers:
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

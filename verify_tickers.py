import requests
import re
from bs4 import BeautifulSoup

def get_official_list():
    print("Fetching full list from malaysiastock.biz...")
    url = "https://www.malaysiastock.biz/Stock-List.aspx"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers)
        # IDs are 4 digits in links like Stock-Quote.aspx?id=1234
        ids = re.findall(r'id=(\d{4})', r.text)
        return sorted(list(set([f"{i}.KL" for i in ids])))
    except:
        return []

if __name__ == "__main__":
    full_list = get_official_list()
    print(f"Total Tickers found: {len(full_list)}")
    if len(full_list) > 500:
        with open('klse_tickers.py', 'w') as f:
            f.write("# Official Full KLSE Ticker List (4-digit codes)\n")
            f.write(f"TICKERS = {full_list}\n")
        print("Updated klse_tickers.py successfully with 4-digit codes.")

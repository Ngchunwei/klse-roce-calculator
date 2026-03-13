import requests
import re

def get_tickers():
    print("Attempting to get all Bursa tickers...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    }
    
    tickers = set()
    
    # Source 1: malaysiastock.biz heatmap or list
    try:
        urls = [
            "https://www.malaysiastock.biz/Stock-List.aspx",
            "https://www.malaysiastock.biz/Market-Watch.aspx"
        ]
        for url in urls:
            r = requests.get(url, headers=headers, timeout=10)
            # Find codes like (1234)
            codes = re.findall(r'\((\d{4})\)', r.text)
            for c in codes: tickers.add(f"{c}.KL")
            # Find codes like id=1234
            ids = re.findall(r'id=(\d{4})', r.text)
            for i in ids: tickers.add(f"{i}.KL")
    except Exception as e:
        print(f"Source 1 error: {e}")

    # Source 2: klsescreener.com
    try:
        url = "https://www.klsescreener.com/v2/stocks"
        r = requests.get(url, headers=headers, timeout=10)
        # Codes are in links like /v2/stocks/view/1234
        codes = re.findall(r'/view/(\d{4})', r.text)
        for c in codes: tickers.add(f"{c}.KL")
    except Exception as e:
        print(f"Source 2 error: {e}")

    return sorted(list(tickers))

if __name__ == "__main__":
    all_tickers = get_tickers()
    print(f"Total Tickers Found: {len(all_tickers)}")
    if len(all_tickers) > 500:
        with open('klse_tickers.py', 'w') as f:
            f.write(f"TICKERS = {all_tickers}\n")
        print("Updated klse_tickers.py successfully.")
    else:
        # Fallback: if we still can't get them, use a pre-defined large list
        print("Failed to get enough tickers. Using fallback list.")

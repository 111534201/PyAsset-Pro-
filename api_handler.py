import yfinance as yf
import requests
import pandas as pd

# !!! 請將 "YOUR_API_KEY" 換成你自己的 API KEY !!!
EXCHANGE_RATE_API_KEY = "115a6bd3ffa3ce393ddb1807"
BASE_CURRENCY = "TWD"


def get_stock_price(symbol):
    try:
        stock = yf.Ticker(symbol)
        # 嘗試多個可能的 key
        price = stock.info.get('currentPrice') or stock.info.get('regularMarketPrice') or stock.info.get('ask')
        if price:
            return float(price)

        # 如果 info 抓不到，嘗試用 fast_info (某些版本 yfinance 較穩)
        if hasattr(stock, 'fast_info'):
            return float(stock.fast_info.last_price)

        return 0.0
    except Exception:
        return 0.0


def get_crypto_price(crypto_id):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto_id}&vs_currencies={BASE_CURRENCY.lower()}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        price = data.get(crypto_id, {}).get(BASE_CURRENCY.lower())
        if price:
            return float(price)
        return 0.0
    except Exception:
        return 0.0


def get_exchange_rates(base_currency="TWD"):
    if EXCHANGE_RATE_API_KEY == "YOUR_API_KEY":
        return None
    url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/latest/{base_currency}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get("result") == "success":
            return data.get("conversion_rates")
        return None
    except Exception:
        return None


def get_exchange_rates_usd_base():
    if EXCHANGE_RATE_API_KEY == "YOUR_API_KEY":
        return None
    url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/latest/USD"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get("result") == "success":
            return data.get("conversion_rates")
        return None
    except Exception:
        return None


# --- 驗證股票 ---
def validate_stock_symbol(symbol):
    try:
        ticker = yf.Ticker(symbol)
        # 透過抓取 history 來確認代號是否有效 (比 info 更快且穩)
        hist = ticker.history(period="1d")
        if hist.empty:
            return None

        info = ticker.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or hist['Close'].iloc[-1]

        return {
            "name": info.get('longName') or info.get('shortName') or symbol,
            "currency": info.get('currency', 'USD').upper(),
            "price": float(current_price),
            "symbol": symbol.upper()
        }
    except Exception as e:
        print(f"Stock Validation Error: {e}")
        return None


# --- 驗證加密貨幣 ---
def validate_crypto_id(user_input):
    search_url = f"https://api.coingecko.com/api/v3/search?query={user_input}"
    try:
        response = requests.get(search_url)
        data = response.json()
        coins = data.get('coins', [])
        target_coin = None

        if not coins: return None

        # 搜尋邏輯
        for coin in coins:
            if coin['symbol'].lower() == user_input.lower():
                target_coin = coin;
                break
        if not target_coin:
            for coin in coins:
                if coin['id'].lower() == user_input.lower():
                    target_coin = coin;
                    break
        if not target_coin: target_coin = coins[0]

        if target_coin:
            real_id = target_coin['id']
            detail_url = f"https://api.coingecko.com/api/v3/coins/{real_id}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false"
            r = requests.get(detail_url)
            if r.status_code == 200:
                d = r.json()
                return {
                    "id": real_id,
                    "name": d.get('name', real_id),
                    "symbol": d.get('symbol', '').upper(),
                    "price": d.get('market_data', {}).get('current_price', {}).get('twd', 0.0)
                }
    except Exception as e:
        print(f"Crypto Validation Error: {e}")
        return None
    return None


# --- [本次報錯缺失的函式] 抓取歷史走勢 ---
def get_historical_data(symbol, time_range):
    """
    根據時間範圍抓取歷史股價
    time_range: '1D', '1W', '1M', '1Y', 'All'
    """
    period_map = {
        '1D': '1d',
        '1W': '5d',
        '1M': '1mo',
        '1Y': '1y',
        'All': 'max'
    }

    interval_map = {
        '1D': '5m',  # 1天看 5分鐘線
        '1W': '1h',  # 1週看 1小時線
        '1M': '1d',  # 1月看 日線
        '1Y': '1d',  # 1年看 日線
        'All': '1wk'  # 全部看 週線
    }

    p = period_map.get(time_range, '1mo')
    i = interval_map.get(time_range, '1d')

    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period=p, interval=i)

        if history.empty:
            return None

        # 整理 DataFrame
        history = history.reset_index()
        # 統一欄位名稱 (yfinance 的 Date 有時有時區)
        if 'Date' in history.columns:
            history['Datetime'] = history['Date']

        # 只要時間跟收盤價
        return history[['Datetime', 'Close']]

    except Exception as e:
        print(f"Fetch history failed for {symbol}: {e}")
        return None
import json
import os
import csv
import datetime

# 定義檔案名稱常數
PORTFOLIO_FILE = 'portfolio.json'
TRANSACTIONS_FILE = 'transactions.json'
REALIZED_PNL_FILE = 'realized_pnl.json'
HISTORY_FILE = 'history.csv'


# --- 讀取與儲存投資組合 (Portfolio) ---
def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 確保基本的 key 存在，避免後續報錯
            if 'stocks' not in data: data['stocks'] = []
            if 'crypto' not in data: data['crypto'] = []
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        # 如果檔案不存在或壞掉，回傳預設空結構
        return {"stocks": [], "crypto": []}


def save_portfolio(data):
    try:
        with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"儲存 Portfolio 失敗: {e}")


# --- 讀取與儲存交易紀錄 (Transactions) ---
def load_transactions():
    try:
        with open(TRANSACTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_transactions(data):
    try:
        with open(TRANSACTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"儲存 Transactions 失敗: {e}")


# --- 讀取與儲存已實現損益 (Realized PnL) ---
def load_realized_pnl():
    try:
        with open(REALIZED_PNL_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_realized_pnl(data):
    try:
        with open(REALIZED_PNL_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"儲存損益失敗: {e}")


# --- 更新與讀取歷史淨值 (History CSV) ---
def update_history(total_net_worth):
    """
    每天只記錄一筆最新的總資產
    """
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    history_data = []

    # 1. 讀取現有紀錄
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                history_data = list(reader)
        except Exception:
            history_data = []

    # 2. 檢查今天是否已經記過 (若有，則更新最後一筆；若無，則新增)
    # 格式: [Date, NetWorth]
    new_entry = [today_str, str(total_net_worth)]

    if history_data and history_data[-1][0] == today_str:
        history_data[-1] = new_entry  # 更新今日數據
    else:
        history_data.append(new_entry)  # 新增今日數據

    # 3. 寫回檔案
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(history_data)
    except IOError as e:
        print(f"寫入歷史失敗: {e}")


def load_history():
    """回傳 DataFrame 所需的 dict list"""
    data = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        data.append({"Date": row[0], "NetWorth": float(row[1])})
        except Exception:
            pass
    return data
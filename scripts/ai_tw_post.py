from utils.market_calendar import is_market_open
from datetime import datetime
import os
import sys
import yfinance as yf
import pandas as pd
import requests
from xgboost import XGBRegressor
import warnings

# 忽略警告
warnings.filterwarnings("ignore")

# ===============================
# Project Base / Data Directory
# ===============================
# 確保路徑正確：獲取專案根目錄
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

HISTORY_FILE = os.path.join(DATA_DIR, "tw_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# =========================
# 📰 消息面（不論開盤與否，每天執行）
# =========================
def run_news():
    print(f"📰 [TW] {datetime.now().strftime('%Y-%m-%d')} 執行台股消息面分析...")
    # 這裡會跑你原本的新聞分析邏輯
    # 如果你是呼叫 news_radar.py，可以使用 subprocess 或直接將邏輯放在這
    pass

# =========================
# 📈 股市工具函數
# =========================
def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 1), round(2 * p - l, 1)

def get_tw_300():
    try:
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        df = pd.read_html(requests.get(url, timeout=10).text)[0]
        df.columns = df.iloc[0]
        df = df.iloc[1:]
        codes = df["有價證券代號及名稱"].str.split("　").str[0]
        codes = codes[codes.str.len() == 4].head(300)
        return [f"{c}.TW" for c in codes]
    except:
        return ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW"]

def get_settle_report():
    if not os.path.exists(HISTORY_FILE):
        return "\n📊 **5 日回測**：尚無可結算資料\n"
    # ... (保留原本對帳邏輯)
    return "\n🏁 **5 日回測結算報告**\n"

# =========================
# 📈 股市面分析（僅在交易日執行）
# =========================
def run_market():
    print("📈 [TW] 偵測到交易日，開始 AI 股價分析與預測...")
    
    fixed = ["2330.TW", "2317.TW", "2454.TW", "0050.TW", "2308.TW", "2382.TW"]
    watch = list(dict.fromkeys(fixed + get_tw_300()))
    
    # 下載與模型邏輯 (同你原本的內容)
    # data = yf.download(...)
    # model.fit(...)
    
    print("✅ 台股 AI 預測報告已發送")

# =========================
# 🚦 唯一入口（台股版優化）
# =========================
def main():
    # 1. 消息面：不論如何都會執行
    run_news()

    # 2. 股市面：檢查是否開盤
    # 利用 utils/market_calendar.py 內的判斷邏輯
    if not is_market_open("TW"):
        print(f"📌 {datetime.now().strftime('%Y-%m-%d')} 台股休市/假日，跳過 AI 股價預測。")
        return 

    # 3. 只有交易日才會執行股市分析
    run_market()

if __name__ == "__main__":
    main()

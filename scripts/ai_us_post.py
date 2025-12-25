from datetime import datetime
import os
import sys
import yfinance as yf
import pandas as pd
import requests
from xgboost import XGBRegressor
import warnings

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

HISTORY_FILE = os.path.join(DATA_DIR, "us_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

def is_us_market_open():
    today = datetime.utcnow().date()
    if datetime.utcnow().weekday() >= 5: return False
    df = yf.download("SPY", start=today, end=today + pd.Timedelta(days=1), progress=False)
    return not df.empty

def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 2), round(2 * p - l, 2)

def get_sp500():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        df = pd.read_html(requests.get(url, headers=headers, timeout=10).text)[0]
        return [s.replace(".", "-") for s in df["Symbol"]]
    except:
        return ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]

def run_market():
    print("📈 [US] 執行美股 AI 分析")
    mag_7 = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]
    watch = list(dict.fromkeys(mag_7 + get_sp500()))
    data = yf.download(watch, period="2y", auto_adjust=True, group_by="ticker", progress=False)

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}
    for s in watch:
        try:
            df = data[s].dropna()
            if len(df) < 150: continue
            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1
            train = df.iloc[:-5].dropna()
            model = XGBRegressor(n_estimators=120, max_depth=3, learning_rate=0.05, random_state=42)
            model.fit(train[feats], train["target"])
            pred = float(model.predict(df[feats].iloc[-1:])[0])
            sup, res = calc_pivot(df)
            results[s] = {"pred": pred, "price": round(df["Close"].iloc[-1], 2), "sup": sup, "res": res}
        except: continue

    msg = f"📊 **美股 AI 進階預測報告 ({datetime.now():%Y-%m-%d})**\n\n💡 AI 為機率模型，僅供研究參考"
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)
    else: print(msg)

def main():
    if not is_us_market_open():
        print(f"📌 {datetime.now():%Y-%m-%d} 美股休市，跳過分析報告。")
        return 
    run_market()

if __name__ == "__main__":
    main()

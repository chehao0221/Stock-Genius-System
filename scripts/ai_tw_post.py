import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
from xgboost import XGBRegressor
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "tw_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# =========================
# 基礎工具
# =========================
def safe_post(msg: str):
    if not WEBHOOK_URL:
        print("⚠️ 未設定 DISCORD_WEBHOOK_URL，僅輸出訊息")
        print(msg)
        return
    try:
        requests.post(WEBHOOK_URL, json={"content": msg}, timeout=10)
    except Exception as e:
        print("Discord 發送失敗：", e)

def add_features(df: pd.DataFrame):
    df = df.copy()
    df["r"] = df["Close"].pct_change()
    df["ma5"] = df["Close"].rolling(5).mean()
    df["ma20"] = df["Close"].rolling(20).mean()
    df["vol"] = df["Volume"].pct_change()
    df = df.dropna()
    return df

# =========================
# 股票池（TW 上市櫃）
# =========================
def get_tw_300_pool():
    try:
        return [
            "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2412.TW",
            "2881.TW", "2882.TW", "1301.TW", "1303.TW", "2002.TW"
        ]
    except:
        return []

# =========================
# 單股預測
# =========================
def predict_stock(symbol):
    try:
        df = yf.download(symbol, period="2y", interval="1d", progress=False)
        if len(df) < 120:
            return None

        df = add_features(df)
        if len(df) < 60:
            return None

        X = df[["r", "ma5", "ma20", "vol"]]
        y = df["r"].shift(-5).dropna()
        X = X.iloc[:-5]

        if len(X) < 30:
            return None

        model = XGBRegressor(
            n_estimators=200,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42
        )
        model.fit(X, y)

        pred = model.predict(X.iloc[-1:])[0]
        last = df.iloc[-1]

        return {
            "p": float(pred),
            "c": float(last["Close"]),
            "s": float(last["Low"]),
            "r": float(last["High"])
        }
    except Exception as e:
        print(f"{symbol} 預測失敗：{e}")
        return None

# =========================
# 主流程
# =========================
def run():
    pool = get_tw_300_pool()
    results = {}

    for s in pool:
        r = predict_stock(s)
        if r:
            results[s] = r

    if not results:
        safe_post("⚠️ 今日無可用預測結果")
        return

    msg = f"📊 **台股 AI 預測報告** ({datetime.now():%Y-%m-%d})\n\n"

    top = sorted(results.items(), key=lambda x: x[1]["p"], reverse=True)[:5]
    for s, i in top:
        msg += f"⭐ **{s}**：`{i['p']:+.2%}`\n"
        msg += f"└ 現價 {i['c']:.1f}｜支撐 {i['s']:.1f}｜壓力 {i['r']:.1f}\n"

    msg += "\n💡 *AI 為未來 5 個交易日的機率性預估，非投資建議*"
    safe_post(msg)

if __name__ == "__main__":
    run()

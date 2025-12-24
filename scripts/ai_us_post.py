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
HISTORY_FILE_US = os.path.join(BASE_DIR, "us_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# 使用您提供的 get_us_300_pool 邏輯
def get_us_pool():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers=headers, timeout=10)
        df = pd.read_html(res.text)[0]
        return [s.replace('.', '-') for s in df['Symbol'].tolist()[:300]]
    except: return ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]

def run_us():
    mag_7 = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]
    pool = get_us_pool()
    all_watch = list(dict.fromkeys(mag_7 + pool))
    
    all_data = yf.download(all_watch, period="2y", auto_adjust=True, group_by="ticker", progress=False)
    results = {}
    
    for s in all_watch:
        try:
            df = all_data[s].dropna()
            df["mom20"], df["bias"], df["vol_ratio"] = df["Close"].pct_change(20), (df["Close"] - df["Close"].rolling(20).mean())/df["Close"].rolling(20).mean(), df["Volume"]/df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1
            model = XGBRegressor(n_estimators=100).fit(df.dropna().iloc[-300:][["mom20", "bias", "vol_ratio"]], df.dropna().iloc[-300:]["target"])
            pred = float(model.predict(df[["mom20", "bias", "vol_ratio"]].iloc[-1:])[0])
            results[s] = {"p": pred, "c": float(df["Close"].iloc[-1])}
        except: continue

    top_5 = sorted({k: v for k, v in results.items() if k not in mag_7}, key=lambda x: results[x]["p"], reverse=True)[:5]
    msg = f"🇺🇸 **美股 AI 進階預測報告 ({datetime.now():%m/%d})**\n🏆 **AI 海選 Top 5**\n"
    for i, s in enumerate(top_5): msg += f"{['🥇','🥈','🥉','📈','📈'][i]} **{s}**: `{results[s]['p']:+.2%}` | 現價 `{results[s]['c']:.2f}`\n"
    msg += "\n💎 **科技巨頭監控**\n"
    for s in mag_7: msg += f"**{s}**: `{results[s]['p']:+.2%}`\n"
    
    from __main__ import settle_predictions # 複用結算邏輯
    final_report = msg + settle_predictions(HISTORY_FILE_US, "美股")
    requests.post(WEBHOOK_URL, json={"content": final_report})

    new_hist = [{"date": datetime.now().date(), "symbol": s, "pred_p": results[s]['c'], "pred_ret": results[s]['p'], "settled": "False"} for s in (top_5 + mag_7)]
    pd.DataFrame(new_hist).to_csv(HISTORY_FILE_US, mode='a', header=not os.path.exists(HISTORY_FILE_US), index=False)

if __name__ == "__main__":
    run_us()

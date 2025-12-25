from utils.market_calendar import is_market_open
from datetime import datetime
import os
import sys
import yfinance as yf
import pandas as pd
import requests
from xgboost import XGBRegressor
import warnings

warnings.filterwarnings("ignore")

# ===============================
# Project Base / Data Directory
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

HISTORY_FILE = os.path.join(DATA_DIR, "tw_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

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
    except Exception:
        return ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW"]

def get_settle_report():
    if not os.path.exists(HISTORY_FILE):
        return "\n📊 **5 日回測**：尚無可結算資料\n"
    try:
        df = pd.read_csv(HISTORY_FILE)
        unsettled = df[df["settled"] == False]
        if unsettled.empty: return "\n📊 **5 日回測**：尚無可結算資料\n"
        
        report = "\n🏁 **5 日回測結算報告**\n"
        for idx, row in unsettled.iterrows():
            try:
                price_df = yf.download(row["symbol"], period="7d", auto_adjust=True, progress=False)
                exit_price = price_df["Close"].iloc[-1]
                entry_p = row["pred_p"] / (1 + row["pred_ret"]) # 根據你的 CSV 結構逆推或直接存 price
                ret = (exit_price - entry_p) / entry_p
                win = (ret > 0 and row["pred_ret"] > 0) or (ret < 0 and row["pred_ret"] < 0)
                report += f"• `{row['symbol']}` 預估 {row['pred_ret']:+.2%} | 實際 `{ret:+.2%}` {'✅' if win else '❌'}\n"
                df.at[idx, "settled"] = True
            except: continue
        df.to_csv(HISTORY_FILE, index=False)
        return report
    except: return ""

def run_market():
    print("📈 [TW] 執行台股 AI 預測分析")
    fixed = ["2330.TW", "2317.TW", "2454.TW", "0050.TW", "2308.TW", "2382.TW"]
    watch = list(dict.fromkeys(fixed + get_tw_300()))
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

    msg = f"📊 **台股 AI 進階預測報告 ({datetime.now():%Y-%m-%d})**\n"
    msg += get_settle_report()
    # 這裡可以加入 top 5 推薦標的邏輯
    msg += "\n💡 AI 為機率模型，僅供研究參考"
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)
    else: print(msg)

def main():
    # 核心邏輯：休市就跳過，不執行 run_market()
    if not is_market_open("TW"):
        print(f"📌 {datetime.now():%Y-%m-%d} 台股休市，跳過分析報告。")
        return 
    run_market()

if __name__ == "__main__":
    main()

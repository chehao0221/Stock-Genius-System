import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
from xgboost import XGBRegressor
from datetime import datetime
import warnings

# =========================
# 基本設定
# =========================
warnings.filterwarnings("ignore")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "tw_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# =========================
# 股票池
# =========================
def get_tw_300_pool():
    try:
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        res = requests.get(url, timeout=10)
        df = pd.read_html(res.text)[0]
        df.columns = df.iloc[0]
        df = df.iloc[1:]
        df["code"] = df["有價證券代號及名稱"].str.split("　").str[0]
        stocks = df[df["code"].str.len() == 4]["code"].tolist()
        return [f"{s}.TW" for s in stocks[:300]]
    except Exception as e:
        return ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW", "0050.TW"]

# =========================
# 大盤環境
# =========================
def get_market_context():
    try:
        idx = yf.download("^TWII", period="1y", auto_adjust=True, progress=False)
        if idx.empty: return True, 0, 0, None
        idx["ma60"] = idx["Close"].rolling(60).mean()
        curr_p = float(idx["Close"].iloc[-1])
        ma60_p = float(idx["ma60"].iloc[-1])
        return curr_p > ma60_p, curr_p, ma60_p, idx
    except: return True, 0, 0, None

def compute_features(df, market_df=None):
    df = df.copy()
    df["mom20"] = df["Close"].pct_change(20)
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    df["ma20"] = df["Close"].rolling(20).mean()
    df["bias"] = (df["Close"] - df["ma20"]) / (df["ma20"] + 1e-9)
    df["vol_ratio"] = df["Volume"] / (df["Volume"].rolling(20).mean() + 1e-9)
    
    hl, hc, lc = df["High"] - df["Low"], (df["High"] - df["Close"].shift()).abs(), (df["Low"] - df["Close"].shift()).abs()
    df["atr"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()

    if market_df is not None:
        mkt_ret = market_df["Close"].pct_change(20)
        df["rs_index"] = df["Close"].pct_change(20) - mkt_ret.reindex(df.index).fillna(0)
    else: df["rs_index"] = 0
    df["avg_amount"] = (df["Close"] * df["Volume"]).rolling(5).mean()
    return df

# =========================
# 主分析流程
# =========================
def run():
    is_bull, mkt_p, mkt_ma, mkt_df = get_market_context()
    must_watch = ["2330.TW", "2317.TW", "2454.TW", "0050.TW"]
    watch = list(dict.fromkeys(must_watch + get_tw_300_pool()))

    print(f"🚀 台股 AI 強制分析啟動 | 指數: {mkt_p:.0f}")

    all_data = yf.download(watch, period="2y", group_by="ticker", auto_adjust=True, progress=False)
    feats = ["mom20", "rsi", "bias", "vol_ratio", "rs_index"]
    results = {}
    
    # 再次降門檻：3000萬成交額即可 (極致放寬)
    MIN_AMOUNT = 30_000_000 

    for s in watch:
        try:
            if s not in all_data or all_data[s].empty: continue
            df = all_data[s].dropna()
            if len(df) < 60: continue
            df = compute_features(df, market_df=mkt_df)
            last = df.iloc[-1]

            if last["avg_amount"] < MIN_AMOUNT: continue

            df["target"] = df["Close"].shift(-5) / df["Close"] - 1
            train = df.dropna().iloc[-250:] 
            if len(train) < 60: continue

            model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
            model.fit(train[feats], train["target"])

            pred = float(model.predict(df[feats].iloc[-1:])[0])
            
            # 這裡取消歸零門檻，只做環境乘數
            if not is_bull: pred *= 0.6

            results[s] = {
                "p": pred,
                "c": float(last["Close"]),
                "rs": float(last["rs_index"])
            }
        except: continue

    # 排序：取出前 5 名，不論報酬率是否大於 0
    horses = {k: v for k, v in results.items() if k not in must_watch}
    top_keys = sorted(horses, key=lambda x: horses[x]["p"], reverse=True)[:5]

    msg = f"🇹🇼 **台股 AI 盤勢掃描 ({datetime.now():%m/%d})**\n"
    msg += f"{'📈 多頭環境' if is_bull else '⚠️ 震盪防護'} | 指數: {mkt_p:.0f}\n"
    msg += "----------------------------------\n"

    if not top_keys:
        msg += "💡 資料量不足，無法生成報告。\n"
    else:
        for i, s in enumerate(top_keys):
            r = results[s]
            # 信心標籤
            signal = "⭐" if r['p'] > 0.005 else ("✅" if r['p'] > 0 else "❓")
            msg += f"{['🥇','🥈','🥉','🎯','🎯'][i]} **{s}** 預估 `{r['p']:+.2%}` | 訊號:{signal}\n"

    msg += "\n🔍 **權值監測**\n"
    for s in must_watch:
        if s in results:
            msg += f"`{s}` 預估 `{results[s]['p']:+.2%}`\n"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)
    else: print(msg)

if __name__ == "__main__":
    run()

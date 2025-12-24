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

def get_market_context():
    try:
        idx = yf.download("^TWII", period="1y", auto_adjust=True, progress=False)
        if idx.empty: return True, 0, 0, None
        idx["ma60"] = idx["Close"].rolling(60).mean()
        curr_p = float(idx["Close"].iloc[-1])
        ma60_p = float(idx["ma60"].iloc[-1])
        return (curr_p > ma60_p), curr_p, ma60_p, idx
    except:
        return True, 0, 0, None

def compute_features(df, market_df=None):
    df = df.copy()
    df["mom20"] = df["Close"].pct_change(20)
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    df["ma20"] = df["Close"].rolling(20).mean()
    df["bias"] = (df["Close"] - df["ma20"]) / (df["ma20"] + 1e-9)
    df["vol_ratio"] = df["Volume"] / (df["Volume"].rolling(20).mean() + 1e-9)
    
    if market_df is not None:
        df["rs_index"] = df["Close"].pct_change(20) - market_df["Close"].pct_change(20).reindex(df.index)
    else:
        df["rs_index"] = 0
    
    return df

def run():
    is_bull, mkt_p, mkt_ma, mkt_df = get_market_context()
    
    # --- 自定義修改：在此輸入您要觀察的特定標的 ---
    target_stocks = ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW", "0050.TW"]
    
    print(f"🚀 台股 AI 分析啟動... (指定標的模式)")
    all_data = yf.download(target_stocks, period="5y", group_by="ticker", auto_adjust=True, progress=False)
    
    feats = ["mom20", "rsi", "bias", "vol_ratio", "rs_index"]
    results = {}

    for s in target_stocks:
        try:
            df = all_data[s].dropna()
            # 降低長度門檻，只要足以計算特徵即可
            if len(df) < 30: continue
            
            df = compute_features(df, market_df=mkt_df)
            last = df.iloc[-1]

            # 準備訓練資料
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1
            train = df.dropna().iloc[-500:] 
            if len(train) < 10: continue # 極低門檻

            model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.03, 
                                 subsample=0.8, colsample_bytree=0.8, random_state=42)
            model.fit(train[feats], train["target"])
            
            # 預測並移除限制
            pred = float(model.predict(train[feats].iloc[-1:])[0])
            
            results[s] = {"p": pred, "c": float(last["Close"]), "rs": float(last.get("rs_index", 0))}
        except Exception as e:
            print(f"無法分析 {s}: {e}")
            continue

    # 輸出訊息
    msg = f"🇹🇼 **台股 AI 指定標的預報 ({datetime.now():%m/%d})**\n"
    msg += f"指數狀況: {mkt_p:.0f} ({'多頭' if is_bull else '空頭'})\n"
    msg += "----------------------------------\n"
    
    if not results:
        msg += "💡 無法取得指定標的之數據。\n"
    else:
        # 按照預測報酬率排序輸出
        sorted_keys = sorted(results, key=lambda x: results[x]['p'], reverse=True)
        for s in sorted_keys:
            r = results[s]
            msg += f"🔹 **{s}** 預估 `{r['p']:+.2%}` | 現價: {r['c']:.1f}\n"
    
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)
    else:
        print(msg)

if __name__ == "__main__":
    run()

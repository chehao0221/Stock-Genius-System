import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import warnings
from xgboost import XGBRegressor
from datetime import datetime, timedelta

# =========================
# 基本設定與環境初始化
# =========================
warnings.filterwarnings("ignore")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "us_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

def get_us_300_pool():
    """從維基百科獲取 S&P 500 前 300 檔標的，若失敗則回傳預設清單"""
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10)
        df = pd.read_html(res.text)[0]
        return [s.replace('.', '-') for s in df['Symbol'].tolist()[:300]]
    except Exception:
        return ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]

def safe_post(msg: str):
    """發送 Discord 通知，若無 Webhook 則僅在終端機列印"""
    if not WEBHOOK_URL:
        print("\n--- Discord 訊息預覽 ---\n", msg)
        return
    try:
        requests.post(WEBHOOK_URL, json={"content": msg}, timeout=15)
    except Exception as e:
        print(f"發送失敗: {e}")

def compute_features(df):
    """計算技術指標特徵"""
    df = df.copy()
    # 動能指標
    df["r"] = df["Close"].pct_change()
    df["mom20"] = df["Close"].pct_change(20)
    
    # RSI 指標
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    
    # 乖離率與量能比
    df["ma20"] = df["Close"].rolling(20).mean()
    df["bias"] = (df["Close"] - df["ma20"]) / (df["ma20"] + 1e-9)
    df["vol_ratio"] = df["Volume"] / (df["Volume"].rolling(20).mean() + 1e-9)
    
    # 支撐與壓力
    df["sup"] = df["Low"].rolling(60).min()
    df["res"] = df["High"].rolling(60).max()
    return df

def audit_and_save(results, top_keys):
    """對帳 5 日前的預測結果，並記錄今日預測"""
    if os.path.exists(HISTORY_FILE):
        hist = pd.read_csv(HISTORY_FILE)
        hist["date"] = pd.to_datetime(hist["date"]).dt.date
    else:
        hist = pd.DataFrame(columns=["date", "symbol", "pred_p", "pred_ret", "settled"])
    
    audit_msg = ""
    today = datetime.now().date()
    deadline = today - timedelta(days=8) # 考慮假日，檢查約 5-8 天前的預測
    unsettled = hist[(hist["settled"] == False) & (hist["date"] <= deadline)]
    
    if not unsettled.empty:
        audit_msg = "\n🎯 **5 日預測結算對帳 (US)**\n"
        for idx, r in unsettled.iterrows():
            try:
                p_df = yf.Ticker(r["symbol"]).history(period="5d")
                if p_df.empty: continue
                curr_p = p_df["Close"].iloc[-1]
                act_ret = (curr_p - r["pred_p"]) / r["pred_p"]
                hit = "✅" if np.sign(act_ret) == np.sign(r["pred_ret"]) else "❌"
                audit_msg += f"`{r['symbol']}` {r['pred_ret']:+.2%} ➜ {act_ret:+.2%} {hit}\n"
                hist.at[idx, "settled"] = True
            except: continue
            
    # 新增今日預測標的
    new_rows = [{"date": today, "symbol": s, "pred_p": results[s]["c"], "pred_ret": results[s]["p"], "settled": False} for s in top_keys]
    hist = pd.concat([hist, pd.DataFrame(new_rows)], ignore_index=True).drop_duplicates(subset=["date", "symbol"], keep="last")
    hist.to_csv(HISTORY_FILE, index=False)
    return audit_msg

def run():
    must_watch = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]
    pool = get_us_300_pool()
    watch = list(set(must_watch + pool))
    feats = ["mom20", "rsi", "bias", "vol_ratio"]
    results = {}

    print(f"📅 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"🔍 正在掃描 {len(watch)} 檔美股標的...")
    
    # 批量下載數據
    all_data = yf.download(watch, period="5y", progress=False, group_by="ticker", auto_adjust=True)

    for s in watch:
        try:
            df = all_data[s].dropna()
            if len(df) < 120: continue
            
            df = compute_features(df)
            # 目標：預測 5 日後的報酬率
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1
            
            train = df.dropna()
            if train.empty: continue
            
            model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
            model.fit(train[feats], train["target"])
            
            # 進行預測 (最新一筆數據)
            pred = float(np.clip(model.predict(df[feats].iloc[-1:])[0], -0.15, 0.15))
            last_close = float(df["Close"].iloc[-1])
            
            results[s] = {"p": pred, "c": last_close}
        except:
            continue

    # 排序並挑選前 5 檔
    top_keys = sorted(results, key=lambda x: results[x]["p"], reverse=True)[:5]
    
    # 產出報告
    report = f"🇺🇸 **美股 AI 選股預測 (5日看漲)**\n"
    for s in top_keys:
        report += f"📈 `{s}` | 預估報酬: {results[s]['p']:+.2%} | 現價: ${results[s]['c']:.2f}\n"
    
    # 對帳
    audit_msg = audit_and_save(results, top_keys)
    
    # 發送
    safe_post(report + audit_msg)

if __name__ == "__main__":
    run()

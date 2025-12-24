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

# --- 你可以自定義這裡的指定股票 ---
MUST_WATCH = ["2330.TW", "2317.TW", "2454.TW", "0050.TW"] 

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
    except:
        return ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW", "0050.TW"]

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
    
    hl, hc, lc = df["High"]-df["Low"], (df["High"]-df["Close"].shift()).abs(), (df["Low"]-df["Close"].shift()).abs()
    df["atr"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    
    if market_df is not None:
        df["rs_index"] = df["Close"].pct_change(20) - market_df["Close"].pct_change(20).reindex(df.index)
    else:
        df["rs_index"] = 0
    
    df["avg_amount"] = (df["Close"] * df["Volume"]).rolling(5).mean()
    return df

def audit_and_save(results, report_keys):
    if os.path.exists(HISTORY_FILE):
        hist = pd.read_csv(HISTORY_FILE)
        hist["date"] = pd.to_datetime(hist["date"]).dt.date
    else:
        hist = pd.DataFrame(columns=["date", "symbol", "pred_p", "pred_ret", "settled"])
    
    today = datetime.now().date()
    new_rows = [{"date": today, "symbol": s, "pred_p": results[s]["c"], "pred_ret": results[s]["p"], "settled": False} for s in report_keys]
    hist = pd.concat([hist, pd.DataFrame(new_rows)], ignore_index=True).drop_duplicates(subset=["date", "symbol"], keep="last")
    hist.to_csv(HISTORY_FILE, index=False)

def run():
    is_bull, mkt_p, mkt_ma, mkt_df = get_market_context()
    pool = get_tw_300_pool()
    all_watch = list(set(MUST_WATCH + pool))
    
    print(f"🚀 台股 AI 分析啟動... (大盤:{'多頭' if is_bull else '空頭'})")
    all_data = yf.download(all_watch, period="5y", group_by="ticker", auto_adjust=True, progress=False)
    
    feats = ["mom20", "rsi", "bias", "vol_ratio", "rs_index"]
    results = {}
    MIN_AMOUNT = 100_000_000 # 1億

    for s in all_watch:
        try:
            df = all_data[s].dropna()
            if len(df) < 150: continue
            df = compute_features(df, market_df=mkt_df)
            last = df.iloc[-1]
            
            # --- 門檻檢查：如果不是 MUST_WATCH，才檢查成交量 ---
            if s not in MUST_WATCH:
                if last["avg_amount"] < MIN_AMOUNT: continue

            df["target"] = df["Close"].shift(-5) / df["Close"] - 1
            train = df.dropna().iloc[-500:] 
            if len(train) < 100: continue

            model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.03, 
                                 subsample=0.8, colsample_bytree=0.8, random_state=42)
            model.fit(train[feats], train["target"])
            
            pred = float(np.clip(model.predict(train[feats].iloc[-1:])[0], -0.15, 0.15))
            
            # 風控調整
            if not is_bull: pred *= 0.5
            if last["atr"] > (df["atr"].mean() * 1.5): pred *= 0.8
            
            # --- 門檻檢查：如果不是 MUST_WATCH，才進行 1% 噪音過濾 ---
            if s not in MUST_WATCH:
                if pred < 0.01: pred = 0 

            results[s] = {"p": pred, "c": float(last["Close"]), "rs": float(last["rs_index"])}
        except: continue

    # 分類結果
    must_results = {k: v for k, v in results.items() if k in MUST_WATCH}
    other_results = {k: v for k, v in results.items() if k not in MUST_WATCH}
    
    # 篩選非指定股票的前 5 名 (且預測值大於 0)
    top_others = sorted(other_results, key=lambda x: other_results[x]['p'], reverse=True)[:5]
    top_others = [k for k in top_others if other_results[k]["p"] > 0]

    # 彙整需要報告的所有股票 (指定股票優先)
    report_keys = list(must_results.keys()) + top_others
    audit_and_save(results, report_keys)
    
    # 建立訊息
    msg = f"🇹🇼 **台股 AI 進階預報 ({datetime.now():%m/%d})**\n"
    msg += f"{'📈 多頭環境' if is_bull else '⚠️ 空頭警示 (預測已降權)'} | 指數: {mkt_p:.0f}\n"
    msg += "----------------------------------\n"
    
    # 輸出指定股票
    msg += "📌 **監測清單 (不設門檻)**\n"
    for s in MUST_WATCH:
        if s in results:
            r = results[s]
            msg += f"🔹 {s}: `{r['p']:+.2%}` | 價格: {r['c']}\n"
        else:
            msg += f"🔹 {s}: 數據不足\n"
    
    msg += "\n🔥 **AI 推薦排行 (經門檻過濾)**\n"
    if not top_others:
        msg += "💡 市場訊號不足，建議觀望。\n"
    else:
        for i, s in enumerate(top_others):
            r = results[s]
            msg += f"{['🥇','🥈','🥉','📈','📈'][i]} **{s}** 預估 `{r['p']:+.2%}` | RS:{'強' if r['rs']>0 else '弱'}\n"
    
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)
    else:
        print(msg)

if __name__ == "__main__":
    run()

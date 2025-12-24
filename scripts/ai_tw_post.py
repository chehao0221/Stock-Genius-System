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
        return ["2330.TW", "2317.TW", "2454.TW", "0050.TW", "2308.TW", "2382.TW"]

def get_market_context():
    try:
        idx = yf.download("^TWII", period="1y", auto_adjust=True, progress=False)
        if idx.empty: return True, 0, 0, None
        idx["ma60"] = idx["Close"].rolling(60).mean()
        curr_p, ma60_p = float(idx["Close"].iloc[-1]), float(idx["ma60"].iloc[-1])
        return (curr_p > ma60_p), curr_p, ma60_p, idx
    except:
        return True, 0, 0, None

def compute_features(df, market_df=None):
    df = df.copy()
    df["mom20"] = df["Close"].pct_change(20)
    delta = df["Close"].diff()
    gain, loss = delta.clip(lower=0).rolling(14).mean(), (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    df["ma20"] = df["Close"].rolling(20).mean()
    df["bias"] = (df["Close"] - df["ma20"]) / (df["ma20"] + 1e-9)
    df["vol_ratio"] = df["Volume"] / (df["Volume"].rolling(20).mean() + 1e-9)
    hl, hc, lc = df["High"]-df["Low"], (df["High"]-df["Close"].shift()).abs(), (df["Low"]-df["Close"].shift()).abs()
    df["atr"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    if market_df is not None:
        df["rs_index"] = df["Close"].pct_change(20) - market_df["Close"].pct_change(20).reindex(df.index)
    else: df["rs_index"] = 0
    df["avg_amount"] = (df["Close"] * df["Volume"]).rolling(5).mean()
    return df

def audit_and_save(results, top_keys):
    if os.path.exists(HISTORY_FILE):
        hist = pd.read_csv(HISTORY_FILE)
        hist["date"] = pd.to_datetime(hist["date"]).dt.date
    else: hist = pd.DataFrame(columns=["date", "symbol", "pred_p", "pred_ret", "settled"])
    today = datetime.now().date()
    new_rows = [{"date": today, "symbol": s, "pred_p": results[s]["c"], "pred_ret": results[s]["p"], "settled": False} for s in top_keys]
    hist = pd.concat([hist, pd.DataFrame(new_rows)], ignore_index=True).drop_duplicates(subset=["date", "symbol"], keep="last")
    hist.to_csv(HISTORY_FILE, index=False)

def run():
    is_bull, mkt_p, mkt_ma, mkt_df = get_market_context()
    # 指定標的清單
    must_watch = ["2330.TW", "2317.TW", "2454.TW", "0050.TW"]
    watch = list(set(must_watch + get_tw_300_pool()))
    
    print(f"🚀 台股 AI 分析啟動... (大盤:{'多頭' if is_bull else '空頭'})")
    all_data = yf.download(watch, period="5y", group_by="ticker", auto_adjust=True, progress=False)
    feats = ["mom20", "rsi", "bias", "vol_ratio", "rs_index"]
    results = {}

    for s in watch:
        try:
            df = all_data[s].dropna()
            if len(df) < 150: continue
            df = compute_features(df, market_df=mkt_df)
            last = df.iloc[-1]
            if last["avg_amount"] < 100_000_000 and s not in must_watch: continue

            df["target"] = df["Close"].shift(-5) / df["Close"] - 1
            train = df.dropna().iloc[-500:]
            model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, random_state=42)
            model.fit(train[feats], train["target"])
            pred = float(np.clip(model.predict(train[feats].iloc[-1:])[0], -0.15, 0.15))
            
            raw_p = pred # 保存原始預測
            if not is_bull: pred *= 0.7 
            if last["atr"] > (df["atr"].mean() * 1.5): pred *= 0.8
            if last["Close"] < last["ma20"]: pred *= 0.8
            final_p = pred if pred >= 0.006 else 0 # 推薦門檻

            results[s] = {"p": final_p, "raw": raw_p, "c": float(last["Close"]), "rs": float(last["rs_index"])}
        except: continue

    horses = {k: v for k, v in results.items() if k not in must_watch}
    top_keys = sorted(horses, key=lambda x: horses[x]['p'], reverse=True)[:5]
    final_keys = [k for k in top_keys if horses[k]["p"] > 0]
    audit_and_save(results, final_keys)
    
    # --- 訊息組裝 ---
    msg = f"🇹🇼 **台股 AI 進階預報 ({datetime.now():%m/%d})**\n"
    msg += f"{'📈 多頭環境' if is_bull else '⚠️ 空頭環境 (弱勢保護)'} | 指數: {mkt_p:.0f}\n"
    msg += "----------------------------------\n"
    
    msg += "🏆 **AI 推薦強勢區**\n"
    if not final_keys:
        msg += "💡 暫無高信心標的。\n"
    else:
        for i, s in enumerate(final_keys):
            r = results[s]
            msg += f"{['🥇','🥈','🥉','📈','📈'][i]} **{s}** 預估 `{r['p']:+.2%}` | RS:{'強' if r['rs']>0 else '弱'}\n"

    msg += "\n🔍 **指定/權值監測 (強制顯示)**\n"
    for s in must_watch:
        if s in results:
            r = results[s]
            emoji = "📈" if r['raw'] > 0 else "📉"
            msg += f"{emoji} `{s:7}` 預估 `{r['raw']:+.2%}` (現價: {r['c']:.1f})\n"
    
    if WEBHOOK_URL: requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)
    else: print(msg)

if __name__ == "__main__": run()

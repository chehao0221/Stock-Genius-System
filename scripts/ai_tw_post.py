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
# 股票池 (自動抓取上市前 300 檔)
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
        print(f"池化抓取失敗: {e}")
        return ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW", "0050.TW"]

# =========================
# 大盤環境監測
# =========================
def get_market_context():
    try:
        idx = yf.download("^TWII", period="1y", auto_adjust=True, progress=False)
        if idx.empty:
            return True, 0, 0, None
        idx["ma60"] = idx["Close"].rolling(60).mean()
        curr_p = float(idx["Close"].iloc[-1])
        ma60_p = float(idx["ma60"].iloc[-1])
        # 多頭定義：收盤價高於 60 日均線
        return curr_p > ma60_p, curr_p, ma60_p, idx
    except:
        return True, 0, 0, None

# =========================
# 進階特徵工程
# =========================
def compute_features(df, market_df=None):
    df = df.copy()
    # 趨勢與動量
    df["mom20"] = df["Close"].pct_change(20)
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    # 乖離與量能
    df["ma20"] = df["Close"].rolling(20).mean()
    df["bias"] = (df["Close"] - df["ma20"]) / (df["ma20"] + 1e-9)
    df["vol_ratio"] = df["Volume"] / (df["Volume"].rolling(20).mean() + 1e-9)

    # 波動指標 (ATR)
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"] - df["Close"].shift()).abs()
    df["atr"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()

    # 相對強度指標 (對比大盤)
    if market_df is not None:
        mkt_ret = market_df["Close"].pct_change(20)
        df["rs_index"] = df["Close"].pct_change(20) - mkt_ret.reindex(df.index).fillna(0)
    else:
        df["rs_index"] = 0

    df["avg_amount"] = (df["Close"] * df["Volume"]).rolling(5).mean()
    return df

# =========================
# 紀錄與對帳
# =========================
def audit_and_save(results, top_keys):
    if os.path.exists(HISTORY_FILE):
        hist = pd.read_csv(HISTORY_FILE)
        hist["date"] = pd.to_datetime(hist["date"]).dt.date
    else:
        hist = pd.DataFrame(columns=["date", "symbol", "pred_p", "pred_ret", "settled"])

    today = datetime.now().date()
    new_rows = []

    for s in top_keys:
        if results[s]["c"] <= 0:
            continue
        new_rows.append({
            "date": today,
            "symbol": s,
            "pred_p": results[s]["c"],
            "pred_ret": results[s]["p"],
            "settled": False
        })

    if new_rows:
        hist = pd.concat([hist, pd.DataFrame(new_rows)], ignore_index=True)
        hist = hist.drop_duplicates(subset=["date", "symbol"], keep="last")
        hist.to_csv(HISTORY_FILE, index=False)

# =========================
# 主分析流程
# =========================
def run():
    is_bull, mkt_p, mkt_ma, mkt_df = get_market_context()

    # 設定監測池
    must_watch = ["2330.TW", "2317.TW", "2454.TW", "0050.TW"]
    pool_stocks = get_tw_300_pool()
    watch = list(dict.fromkeys(must_watch + pool_stocks))

    print(f"🚀 台股 AI 分析啟動 | 市場趨勢：{'多頭 (進攻模式)' if is_bull else '空頭 (防守模式)'}")

    # 下載數據
    all_data = yf.download(watch, period="5y", group_by="ticker", auto_adjust=True, progress=False)

    feats = ["mom20", "rsi", "bias", "vol_ratio", "rs_index"]
    results = {}
    
    # --- 智能標準調整 ---
    # 多頭市場放寬成交額至 5000 萬，空頭市場維持 1 億以求安全
    MIN_AMOUNT = 50_000_000 if is_bull else 100_000_000 
    PRED_THRESHOLD = 0.005 # 降低至 0.5% 捕捉小波段機會

    for s in watch:
        try:
            if s not in all_data or all_data[s].empty:
                continue

            df = all_data[s].dropna()
            if len(df) < 150:
                continue

            df = compute_features(df, market_df=mkt_df)
            last = df.iloc[-1]

            # 過濾成交量過低標的
            if last["avg_amount"] < MIN_AMOUNT:
                continue

            # 建立目標：5日後報酬率
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1
            train = df.dropna().iloc[-500:] # 使用最近 500 根 K 線
            
            if len(train) < 100:
                continue

            # 訓練優化後的 XGB 模型
            model = XGBRegressor(
                n_estimators=300,      # 增加迭代次數
                max_depth=3,           # 淺層樹防止過擬合
                learning_rate=0.01,    # 降低學習率追求穩定
                subsample=0.8,
                random_state=42
            )
            model.fit(train[feats], train["target"])

            # 預測最新一筆
            raw_pred = model.predict(df[feats].iloc[-1:])[0]
            pred = float(np.clip(raw_pred, -0.15, 0.15))

            # --- 風險降權邏輯 ---
            if not is_bull:
                pred *= 0.5 # 市場空頭時預期獲利砍半
            if last["atr"] > df["atr"].mean() * 1.5:
                pred *= 0.8 # 波動異常放大時保守看待

            # 過濾低於門檻的信號
            if pred < PRED_THRESHOLD:
                pred = 0

            results[s] = {
                "p": pred,
                "c": float(last["Close"]),
                "rs": float(last["rs_index"])
            }
        except Exception as e:
            continue

    # 分離權值股與黑馬股
    horses = {k: v for k, v in results.items() if k not in must_watch}
    top_keys = sorted(horses, key=lambda x: horses[x]["p"], reverse=True)[:5]
    final_keys = [k for k in top_keys if horses[k]["p"] > 0]

    # 存檔
    audit_and_save(results, final_keys)

    # 組合 Discord 訊息
    msg = f"🇹🇼 **台股 AI 進階分析 ({datetime.now():%m/%d})**\n"
    msg += f"{'📈 多頭環境' if is_bull else '⚠️ 空頭警示'} | 指數: {mkt_p:.0f} | 門檻: {MIN_AMOUNT/100000000:.1f}億\n"
    msg += "----------------------------------\n"

    if not final_keys:
        msg += "💡 目前市場信號不足，建議觀望。\n"
    else:
        for i, s in enumerate(final_keys):
            r = results[s]
            strength = "🔥" if r['rs'] > 0.02 else ("👍" if r['rs'] > 0 else "☁️")
            msg += f"{['🥇','🥈','🥉','📈','📈'][i]} **{s}** 預估 `{r['p']:+.2%}` | RS:{strength}\n"

    msg += "\n🔍 **權值/指數監測**\n"
    for s in must_watch:
        if s in results:
            msg += f"`{s}` 預估 `{results[s]['p']:+.2%}`\n"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)
    else:
        print(msg)

if __name__ == "__main__":
    run()

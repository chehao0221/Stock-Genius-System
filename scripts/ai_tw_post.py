import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
from xgboost import XGBRegressor
from datetime import datetime, timedelta
import warnings

# =========================
# 基本設定
# =========================
warnings.filterwarnings("ignore")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "tw_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# =========================
# 自動結算 (5日後對比)
# =========================
def settle_previous_predictions():
    if not os.path.exists(HISTORY_FILE):
        return ""
    try:
        df = pd.read_csv(HISTORY_FILE)
        if df.empty: return ""
        df['date'] = pd.to_datetime(df['date'])
        today = datetime.now()
        
        # 找出 5-10 天前尚未結算的資料 (避免假日導致漏結)
        mask = (df['settled'].astype(str).str.upper() == 'FALSE') & (df['date'] <= today - timedelta(days=5))
        to_settle = df[mask].copy()
        
        if to_settle.empty: return "\n📊 今日尚無待結算的歷史預測 (需累積 5 天資料)。"

        summary_msg = "\n🏁 **5 日回測結算報告**\n"
        symbols = to_settle['symbol'].unique().tolist()
        current_data = yf.download(symbols, period="5d", auto_adjust=True, progress=False)['Close']
        
        for idx, row in to_settle.iterrows():
            sym = row['symbol']
            try:
                # 取得最新收盤價
                actual_p = float(current_data[sym].dropna().iloc[-1]) if isinstance(current_data, pd.DataFrame) else float(current_data.iloc[-1])
                actual_ret = (actual_p - row['pred_p']) / row['pred_p']
                
                # 判定勝負：方向正確即為贏
                is_win = (actual_ret > 0 and row['pred_ret'] > 0) or (actual_ret < 0 and row['pred_ret'] < 0)
                df.at[idx, 'settled'] = 'True'
                summary_msg += f"• `{sym}`: 預測 {row['pred_ret']:+.2%} | 實際 `{actual_ret:+.2%}` {'✅' if is_win else '❌'}\n"
            except: continue
            
        df.to_csv(HISTORY_FILE, index=False)
        return summary_msg
    except: return ""

# =========================
# 分析與執行
# =========================
def run():
    # 1. 大盤與結算
    idx_df = yf.download("^TWII", period="1y", auto_adjust=True, progress=False)
    curr_mkt_p = float(idx_df["Close"].iloc[-1])
    settle_report = settle_previous_predictions()
    
    # 2. 股票池與資料下載
    # 增加更多熱門股，確保一定有數據
    watch = ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW", "2603.TW", "2609.TW", "2303.TW", "3231.TW", "2357.TW"]
    all_data = yf.download(watch, period="2y", auto_adjust=True, group_by="ticker", progress=False)
    
    results = {}
    feats = ["mom20", "bias", "vol_ratio"] # 縮減特徵，提高穩定性
    
    for s in watch:
        try:
            df = all_data[s].dropna()
            if len(df) < 50: continue
            
            # 簡易特徵計算
            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1
            
            train = df.dropna().iloc[-250:]
            model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
            model.fit(train[feats], train["target"])
            
            pred = float(model.predict(df[feats].iloc[-1:])[0])
            results[s] = {"p": pred, "c": float(df["Close"].iloc[-1])}
        except: continue

    # 3. 排序前 5 名 (強制選出)
    top_keys = sorted(results, key=lambda x: results[x]["p"], reverse=True)[:5]
    
    today_msg = f"🇹🇼 **台股 AI 盤勢分析 ({datetime.now():%m/%d})**\n"
    today_msg += f"指數: {curr_mkt_p:.0f} | 門檻: 數據優先模式\n"
    today_msg += "----------------------------------\n"

    if top_keys:
        new_entries = []
        for s in top_keys:
            r = results[s]
            status = "⭐" if r['p'] > 0.005 else "☁️"
            today_msg += f"🎯 **{s}** 預估 `{r['p']:+.2%}` | 收盤 `{r['c']:.1f}` {status}\n"
            new_entries.append({"date": datetime.now().date(), "symbol": s, "pred_p": r['c'], "pred_ret": r['p'], "settled": "False"})
        
        # 存入歷史
        pd.DataFrame(new_entries).to_csv(HISTORY_FILE, mode='a', header=not os.path.exists(HISTORY_FILE), index=False)
    else:
        today_msg += "⚠️ 暫無有效數據標的。\n"

    final_msg = today_msg + settle_report
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": final_msg[:1900]}, timeout=15)
    else:
        print(final_msg)

if __name__ == "__main__":
    run()

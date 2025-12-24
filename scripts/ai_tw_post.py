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
# 核心：自動結算功能 (5日後對比)
# =========================
def settle_previous_predictions():
    if not os.path.exists(HISTORY_FILE):
        return ""
    
    df = pd.read_csv(HISTORY_FILE)
    if df.empty: return ""
    
    # 找出尚未結算且預測日期超過 5 天前的記錄
    df['date'] = pd.to_datetime(df['date'])
    today = datetime.now()
    
    # 過篩出需要結算的清單 (5到10天前的預測)
    to_settle = df[(df['settled'] == False) & (df['date'] <= today - timedelta(days=5))].copy()
    
    if to_settle.empty:
        return "📊 今日尚無待結算之 5 日前預測。"

    summary_msg = "\n🏁 **5 日回測結算報告**\n"
    symbols = to_settle['symbol'].unique().tolist()
    
    # 一次性抓取最新價格
    current_data = yf.download(symbols, period="5d", interval="1d", progress=False)['Close']
    
    for idx, row in to_settle.iterrows():
        try:
            sym = row['symbol']
            pred_p = row['pred_p'] # 預測當天的收盤價
            
            # 獲取今日實際價格 (最後一個有效收盤價)
            if isinstance(current_data, pd.DataFrame):
                actual_p = float(current_data[sym].dropna().iloc[-1])
            else:
                actual_p = float(current_data.iloc[-1])
                
            actual_ret = (actual_p - pred_p) / pred_p
            is_win = (actual_ret > 0 and row['pred_ret'] > 0) or (actual_ret < 0 and row['pred_ret'] < 0)
            
            df.at[idx, 'settled'] = True
            df.at[idx, 'actual_ret'] = actual_ret
            
            summary_msg += f"• `{sym}`: 預測 {row['pred_ret']:+.2%} | 實際 `{actual_ret:+.2%}` {'✅' if is_win else '❌'}\n"
        except:
            continue
            
    df.to_csv(HISTORY_FILE, index=False)
    return summary_msg

# =========================
# 特徵工程 (加入更多容錯)
# =========================
def compute_features(df, market_df=None):
    df = df.copy()
    # 避免數據太少導致滾動計算出錯，給予最小週期 10
    period = min(20, len(df)//4)
    if period < 5: return None
    
    df["mom20"] = df["Close"].pct_change(period)
    df["ma20"] = df["Close"].rolling(period).mean()
    df["bias"] = (df["Close"] - df["ma20"]) / (df["ma20"] + 1e-9)
    df["vol_ratio"] = df["Volume"] / (df["Volume"].rolling(period).mean() + 1e-9)
    
    if market_df is not None:
        mkt_ret = market_df["Close"].pct_change(period)
        df["rs_index"] = df["Close"].pct_change(period) - mkt_ret.reindex(df.index).fillna(0)
    else:
        df["rs_index"] = 0
        
    df["avg_amount"] = (df["Close"] * df["Volume"]).rolling(5).mean()
    return df

# =========================
# 主程序
# =========================
def run():
    # 1. 先結算舊預測
    settle_report = settle_previous_predictions()
    
    # 2. 環境檢測
    idx_df = yf.download("^TWII", period="1y", auto_adjust=True, progress=False)
    is_bull = float(idx_df["Close"].iloc[-1]) > float(idx_df["Close"].rolling(60).mean().iloc[-1])
    
    # 3. 股票抓取 (改用強迫模式)
    watch = ["2330.TW", "2317.TW", "2454.TW", "0050.TW"] # 您可以自行加入 get_tw_300_pool()
    all_data = yf.download(watch, period="2y", auto_adjust=True, group_by="ticker", progress=False)
    
    results = {}
    feats = ["mom20", "bias", "vol_ratio", "rs_index"]
    
    for s in watch:
        try:
            df = all_data[s].dropna()
            df = compute_features(df, market_df=idx_df)
            if df is None: continue
            
            # 設定預算目標
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1
            train_data = df.dropna()
            
            if len(train_data) < 30: # 極致寬容，只要有30天數據就練
                continue
                
            model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05)
            model.fit(train_data[feats], train_data["target"])
            
            last_feat = df[feats].iloc[-1:].fillna(0)
            pred = float(model.predict(last_feat)[0])
            
            results[s] = {
                "p": pred,
                "c": float(df["Close"].iloc[-1]),
                "rs": float(df["rs_index"].iloc[-1])
            }
        except:
            continue

    # 4. 生成今日報告
    today_msg = f"🇹🇼 **台股 AI 分析 ({datetime.now():%m/%d})**\n"
    today_msg += f"指數: {idx_df['Close'].iloc[-1]:.0f} | 趨勢: {'多頭' if is_bull else '防守'}\n"
    today_msg += "----------------------------------\n"
    
    top_keys = sorted(results, key=lambda x: results[x]["p"], reverse=True)[:5]
    
    if not top_keys:
        today_msg += "⚠️ 今日數據源抓取異常，請稍後再試。"
    else:
        for s in top_keys:
            r = results[s]
            today_msg += f"🎯 **{s}** 預估 `{r['p']:+.2%}` | 收盤 `{r['c']:.1f}`\n"
            
        # 儲存今日預測供未來結算
        new_history = pd.DataFrame([{
            "date": datetime.now().date(),
            "symbol": s,
            "pred_p": results[s]["c"],
            "pred_ret": results[s]["p"],
            "settled": False
        } for s in top_keys])
        
        if os.path.exists(HISTORY_FILE):
            new_history.to_csv(HISTORY_FILE, mode='a', header=False, index=False)
        else:
            new_history.to_csv(HISTORY_FILE, index=False)

    # 5. 發送整合訊息
    final_msg = today_msg + settle_report
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": final_msg[:1900]})
    else:
        print(final_msg)

if __name__ == "__main__":
    run()

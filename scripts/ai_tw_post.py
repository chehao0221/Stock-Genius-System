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
# 5 日回測結算 (自動對比)
# =========================
def settle_previous_predictions():
    if not os.path.exists(HISTORY_FILE):
        return ""
    
    try:
        df = pd.read_csv(HISTORY_FILE)
        if df.empty: return ""
        
        df['date'] = pd.to_datetime(df['date'])
        today = datetime.now()
        
        # 找出尚未結算且預測超過 5 天前的記錄
        mask = (df['settled'].astype(str) == 'False') & (df['date'] <= today - timedelta(days=5))
        to_settle = df[mask].copy()
        
        if to_settle.empty:
            return "\n📊 今日尚無待結算之 5 日前預測。"

        summary_msg = "\n🏁 **5 日回測結算報告**\n"
        symbols = to_settle['symbol'].unique().tolist()
        
        # 抓取對比價格
        current_prices = yf.download(symbols, period="5d", auto_adjust=True, progress=False)['Close']
        
        for idx, row in to_settle.iterrows():
            sym = row['symbol']
            pred_price = row['pred_p']
            
            # 取得最新收盤價並處理 Multi-Index
            if isinstance(current_prices, pd.DataFrame):
                price_series = current_prices[sym].dropna()
            else:
                price_series = current_prices.dropna()
                
            if price_series.empty: continue
            
            actual_p = float(price_series.iloc[-1])
            actual_ret = (actual_p - pred_price) / pred_price
            
            # 判斷方向是否準確
            is_win = (actual_ret > 0 and row['pred_ret'] > 0) or (actual_ret < 0 and row['pred_ret'] < 0)
            
            df.loc[idx, 'settled'] = 'True'
            df.loc[idx, 'actual_ret'] = actual_ret
            
            summary_msg += f"• `{sym}`: 預估 {row['pred_ret']:+.2%} | 實際 `{actual_ret:+.2%}` {'✅' if is_win else '❌'}\n"
            
        df.to_csv(HISTORY_FILE, index=False)
        return summary_msg
    except Exception as e:
        return f"\n⚠️ 結算過程發生錯誤: {str(e)}"

# =========================
# 特徵工程
# =========================
def compute_features(df, market_df=None):
    df = df.copy()
    if len(df) < 30: return None
    
    df["mom20"] = df["Close"].pct_change(20)
    df["ma20"] = df["Close"].rolling(20).mean()
    df["bias"] = (df["Close"] - df["ma20"]) / (df["ma20"] + 1e-9)
    df["vol_ratio"] = df["Volume"] / (df["Volume"].rolling(20).mean() + 1e-9)
    
    if market_df is not None:
        mkt_close = market_df["Close"]
        mkt_ret = mkt_close.pct_change(20)
        df["rs_index"] = df["Close"].pct_change(20) - mkt_ret.reindex(df.index).fillna(0)
    else:
        df["rs_index"] = 0
        
    df["avg_amount"] = (df["Close"] * df["Volume"]).rolling(5).mean()
    return df

# =========================
# 主程序
# =========================
def run():
    # 1. 抓取大盤數據
    idx_df = yf.download("^TWII", period="1y", auto_adjust=True, progress=False)
    if idx_df.empty:
        print("無法抓取大盤數據")
        return

    # 安全地獲取最新收盤價 (解決報錯關鍵)
    curr_mkt_p = float(idx_df["Close"].iloc[-1])
    mkt_ma60 = float(idx_df["Close"].rolling(60).mean().iloc[-1])
    is_bull = curr_mkt_p > mkt_ma60
    
    # 2. 結算 5 日前的預測
    settle_report = settle_previous_predictions()
    
    # 3. 股票分析 (手動指定監測標的以確保穩定)
    watch = ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW", "0050.TW", "2603.TW", "2609.TW"]
    all_data = yf.download(watch, period="2y", auto_adjust=True, group_by="ticker", progress=False)
    
    results = {}
    feats = ["mom20", "bias", "vol_ratio", "rs_index"]
    
    for s in watch:
        try:
            # 處理 Multi-Index 下的 DataFrame
            ticker_df = all_data[s].dropna() if s in all_data.columns.levels[0] else all_data.dropna()
            df = compute_features(ticker_df, market_df=idx_df)
            if df is None: continue
            
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1
            train_data = df.dropna()
            
            if len(train_data) < 40: continue
                
            model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
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

    # 4. 組合 Discord 訊息
    today_msg = f"🇹🇼 **台股 AI 分析 ({datetime.now():%m/%d})**\n"
    today_msg += f"指數: {curr_mkt_p:.0f} | 趨勢: {'多頭' if is_bull else '防守'}\n"
    today_msg += "----------------------------------\n"
    
    # 選出前 5 名
    top_keys = sorted(results, key=lambda x: results[x]["p"], reverse=True)[:5]
    
    if not top_keys:
        today_msg += "💡 目前市場波動極小，AI 尚未偵測到顯著訊號。"
    else:
        new_hist_entries = []
        for s in top_keys:
            r = results[s]
            today_msg += f"🎯 **{s}** 預估 `{r['p']:+.2%}` | 收盤 `{r['c']:.1f}`\n"
            new_hist_entries.append({
                "date": datetime.now().date(),
                "symbol": s,
                "pred_p": r['c'],
                "pred_ret": r['p'],
                "settled": "False"
            })
        
        # 儲存歷史紀錄
        hist_df = pd.DataFrame(new_hist_entries)
        if not os.path.exists(HISTORY_FILE):
            hist_df.to_csv(HISTORY_FILE, index=False)
        else:
            hist_df.to_csv(HISTORY_FILE, mode='a', header=False, index=False)

    # 5. 合併報告並發送
    final_report = today_msg + settle_report
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": final_report[:1900]}, timeout=15)
    else:
        print(final_report)

if __name__ == "__main__":
    run()

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
from xgboost import XGBRegressor
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings("ignore")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# --- 核心路徑設定 ---
HISTORY_FILE = "data/us_history.csv"

def get_us_300_pool():
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        df = pd.read_html(requests.get(url).text)[0]
        # 處理代號中的點（如 BRK.B 轉為 BRK-B 以符合 yfinance 格式）
        return [s.replace('.', '-') for s in df['Symbol'].tolist()[:300]]
    except: 
        return ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]

def compute_features(df):
    df = df.copy()
    df["mom20"] = df["Close"].pct_change(20)
    df["rsi"] = 100 - (100 / (1 + df["Close"].diff().clip(lower=0).rolling(14).mean() / ((-df["Close"].diff().clip(upper=0)).rolling(14).mean() + 1e-9)))
    df["ma20"] = df["Close"].rolling(20).mean()
    df["bias"] = (df["Close"] - df["ma20"]) / (df["ma20"] + 1e-9)
    df["vol_ratio"] = df["Volume"] / (df["Volume"].rolling(20).mean() + 1e-9)
    df["sup"] = df["Low"].rolling(60).min()
    df["res"] = df["High"].rolling(60).max()
    return df

def audit_and_save(current_results, top_5_keys):
    audit_msg = ""
    # 統一使用小寫欄位名以符合規範
    columns = ['date', 'symbol', 'pred_p', 'pred_ret', 'settled']
    
    if os.path.exists(HISTORY_FILE):
        try:
            hist_df = pd.read_csv(HISTORY_FILE)
            # 關鍵修正：解決日期格式混合導致的 ValueError
            hist_df['date'] = pd.to_datetime(hist_df['date'], format='mixed')
            
            # 確保 settled 欄位存在
            if 'settled' not in hist_df.columns: hist_df['settled'] = False
            
            deadline = datetime.now() - timedelta(days=7)
            to_settle = hist_df[(hist_df['date'] <= deadline) & (hist_df['settled'] == False)]
            
            if not to_settle.empty:
                audit_msg = "\n🎯 **5日預估結算對帳單**\n"
                for idx, row in to_settle.iterrows():
                    try:
                        ticker = yf.Ticker(row['symbol'])
                        curr_data = ticker.history(period="1d")
                        if curr_data.empty: continue
                        
                        curr_p = curr_data['Close'].iloc[-1]
                        actual_ret = (curr_p - row['pred_p']) / row['pred_p']
                        is_hit = "✅ 命中" if (actual_ret > 0 and row['pred_ret'] > 0) or (actual_ret < 0 and row['pred_ret'] < 0) else "❌ 錯誤"
                        audit_msg += f"`{row['symbol']}`: 預估 `{row['pred_ret']:+.2%}` ➔ 實際 `{actual_ret:+.2%}` ({is_hit})\n"
                        hist_df.at[idx, 'settled'] = True
                    except: continue
            hist_df.to_csv(HISTORY_FILE, index=False)
        except:
            hist_df = pd.DataFrame(columns=columns)
    else:
        hist_df = pd.DataFrame(columns=columns)

    # 紀錄當前推薦
    new_recs = []
    today_str = datetime.now().strftime("%Y-%m-%d")
    for s in top_5_keys:
        new_recs.append({
            'date': today_str,
            'symbol': s,
            'pred_p': current_results[s]['c'],
            'pred_ret': current_results[s]['p'],
            'settled': False
        })
    
    hist_df = pd.concat([hist_df, pd.DataFrame(new_recs)], ignore_index=True)
    hist_df.to_csv(HISTORY_FILE, index=False)
    return audit_msg

def run():
    if not WEBHOOK_URL: return
    symbols = get_us_300_pool()
    must_watch = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "QQQ", "SPY", "SOXL"]
    all_syms = list(set(symbols + must_watch))
    
    # yfinance 下載
    data = yf.download(all_syms, period="5y", progress=False)
    results = {}
    feats = ["mom20", "rsi", "bias", "vol_ratio"]
    
    for s in all_syms:
        try:
            df = data.xs(s, axis=1, level=1).dropna()
            if len(df) < 60: continue # 資料量不足跳過
            
            df = compute_features(df)
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1
            train = df.dropna()
            
            model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.07)
            model.fit(train[feats], train["target"])
            
            pred = model.predict(df[feats].iloc[-1:])[0]
            results[s] = {
                "p": pred, 
                "c": df["Close"].iloc[-1], 
                "s": df["sup"].iloc[-1], 
                "r": df["res"].iloc[-1]
            }
        except: continue

    # 排除 must_watch 後選取預期回報最高前 5
    pool_results = [s for s in results if s not in must_watch]
    top_5 = sorted(pool_results, key=lambda x: results[x]['p'], reverse=True)[:5]
    
    audit_report = audit_and_save(results, top_5)
    
    # 輸出消息構建
    today = datetime.now().strftime("%Y-%m-%d %H:%M EST")
    msg = f"🇺🇸 **美股 AI 預估報告 ({today})**\n"
    msg += "----------------------------------\n"
    msg += "🏆 **S&P 300 預選前 5 名**\n"
    ranks = ["🥇", "🥈", "🥉", "📈", "📈"]
    for idx, s in enumerate(top_5):
        i = results[s]
        msg += f"{ranks[idx]} **{s}**: `預估 {i['p']:+.2%}`\n"
        msg += f"└ 現價: `${i['c']:.2f}` (支撐: {i['s']:.1f} / 壓力: {i['r']:.1f})\n"
        
    msg += "\n💎 **核心監控清單**\n"
    for s in must_watch:
        if s in results:
            emoji = "🚀" if s in ["TSLA", "SOXL", "NVDA"] else "⭐"
            i = results[s]
            msg += f"{emoji} **{s}**: `預估 {i['p']:+.2%}`\n"
            msg += f"└ 現價: `${i['c']:.2f}` (支撐: {i['s']:.1f} / 壓力: {i['r']:.1f})\n"
            
    msg += audit_report + "\n💡 *註：預估值為對未來 5 個交易日後的走勢判斷。*"
    requests.post(WEBHOOK_URL, json={"content": msg})

if __name__ == "__main__":
    run()

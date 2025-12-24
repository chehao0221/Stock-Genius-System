import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
from xgboost import XGBRegressor
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings("ignore")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE_TW = os.path.join(BASE_DIR, "tw_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

def settle_predictions(history_path, market_name):
    if not os.path.exists(history_path): return ""
    try:
        df = pd.read_csv(history_path)
        df['date'] = pd.to_datetime(df['date'])
        mask = (df['settled'].astype(str).str.upper() == 'FALSE') & (df['date'] <= datetime.now() - timedelta(days=5))
        to_settle = df[mask].copy()
        if to_settle.empty: return f"\n📊 {market_name} 尚無待結算數據。"
        
        summary = f"\n🏁 **{market_name} 5日回測結算**\n"
        symbols = to_settle['symbol'].unique().tolist()
        current_data = yf.download(symbols, period="5d", auto_adjust=True, progress=False)['Close']
        
        for idx, row in to_settle.iterrows():
            sym = row['symbol']
            try:
                actual_p = float(current_data[sym].dropna().iloc[-1]) if isinstance(current_data, pd.DataFrame) else float(current_data.iloc[-1])
                actual_ret = (actual_p - row['pred_p']) / row['pred_p']
                is_win = (actual_ret > 0 and row['pred_ret'] > 0) or (actual_ret < 0 and row['pred_ret'] < 0)
                df.at[idx, 'settled'] = 'True'
                summary += f"• `{sym}`: 預估 {row['pred_ret']:+.2%} | 實際 `{actual_ret:+.2%}` {'✅' if is_win else '❌'}\n"
            except: continue
        df.to_csv(history_path, index=False)
        return summary
    except: return ""

def run_tw():
    fixed_watch = ["2330.TW", "2317.TW", "2454.TW", "0050.TW", "2308.TW", "2382.TW"]
    # 這裡插入您之前的 get_tw_300_pool 邏輯
    all_watch = list(dict.fromkeys(fixed_watch + ["2303.TW", "3231.TW", "2603.TW", "2609.TW"])) 
    
    all_data = yf.download(all_watch, period="2y", auto_adjust=True, group_by="ticker", progress=False)
    results = {}
    
    for s in all_watch:
        try:
            df = all_data[s].dropna()
            df["mom20"], df["bias"], df["vol_ratio"] = df["Close"].pct_change(20), (df["Close"] - df["Close"].rolling(20).mean())/df["Close"].rolling(20).mean(), df["Volume"]/df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1
            train = df.dropna().iloc[-250:]
            model = XGBRegressor(n_estimators=100, max_depth=3).fit(train[["mom20", "bias", "vol_ratio"]], train["target"])
            pred = float(model.predict(df[["mom20", "bias", "vol_ratio"]].iloc[-1:])[0])
            results[s] = {"p": pred, "c": float(df["Close"].iloc[-1])}
        except: continue

    top_5 = sorted({k: v for k, v in results.items() if k not in fixed_watch}, key=lambda x: results[x]["p"], reverse=True)[:5]
    msg = f"📊 **台股 AI 進階預測報告 ({datetime.now():%m/%d})**\n🏆 **AI 海選 Top 5**\n"
    for i, s in enumerate(top_5): msg += f"{['🥇','🥈','🥉','📈','📈'][i]} **{s}**: `{results[s]['p']:+.2%}` | 現價 `{results[s]['c']}`\n"
    msg += "\n🔍 **指定權值監控**\n"
    for s in fixed_watch: msg += f"**{s}**: `{results[s]['p']:+.2%}`\n"
    
    final_report = msg + settle_predictions(HISTORY_FILE_TW, "台股")
    requests.post(WEBHOOK_URL, json={"content": final_report})

    new_hist = [{"date": datetime.now().date(), "symbol": s, "pred_p": results[s]['c'], "pred_ret": results[s]['p'], "settled": "False"} for s in (top_5 + fixed_watch)]
    pd.DataFrame(new_hist).to_csv(HISTORY_FILE_TW, mode='a', header=not os.path.exists(HISTORY_FILE_TW), index=False)

if __name__ == "__main__":
    run_tw()

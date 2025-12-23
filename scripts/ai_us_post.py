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
HISTORY_FILE = "data/us_history.csv"

def get_us_300_pool():
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        df = pd.read_html(requests.get(url).text)[0]
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
    df["sup"] = df["Low"].rolling(20).min()
    df["res"] = df["High"].rolling(20).max()
    return df

def audit_and_save(results, top_5):
    if not os.path.exists(HISTORY_FILE):
        df_hist = pd.DataFrame(columns=["date", "symbol", "pred_p", "pred_ret", "settled"])
    else:
        df_hist = pd.read_csv(HISTORY_FILE)

    # 結算 7 天前的預測
    deadline = datetime.now() - timedelta(days=7)
    df_hist['date'] = pd.to_datetime(df_hist['date'])
    
    report = ""
    for idx, row in df_hist[(df_hist['date'] <= deadline) & (df_hist['settled'] == False)].iterrows():
        try:
            ticker = yf.Ticker(row['symbol'])
            current_p = ticker.history(period="1d")['Close'].iloc[-1]
            actual_ret = (current_p - row['pred_p']) / row['pred_p']
            df_hist.at[idx, 'settled'] = True
            df_hist.at[idx, 'actual_ret'] = actual_ret
            status = "✅ 達標" if actual_ret > 0 else "❌ 未達標"
            report += f"• {row['symbol']}: 預估 {row['pred_ret']:.1%}, 實際 {actual_ret:+.1%} {status}\n"
        except: continue
    
    # 加入今日新預測
    new_data = []
    for s in top_5:
        new_data.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "symbol": s,
            "pred_p": results[s]['c'],
            "pred_ret": results[s]['p'],
            "settled": False
        })
    
    df_hist = pd.concat([df_hist, pd.DataFrame(new_data)], ignore_index=True)
    df_hist.to_csv(HISTORY_FILE, index=False)
    return report

def run():
    if not WEBHOOK_URL: return
    symbols = get_us_300_pool()
    results = {}
    feats = ["mom20", "rsi", "bias", "vol_ratio"]
    must_watch = ["NVDA", "TSLA", "AAPL"]

    # 批量抓取資料以提升速度
    data = yf.download(symbols + must_watch, period="2y", interval="1d", group_by='ticker', threads=True)

    for s in symbols + must_watch:
        try:
            df = data[s].dropna()
            if len(df) < 60: continue
            df = compute_features(df)
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1
            train = df.dropna()
            model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.07)
            model.fit(train[feats], train["target"])
            pred = model.predict(df[feats].iloc[-1:])[0]
            results[s] = {"p": pred, "c": df["Close"].iloc[-1], "s": df["sup"].iloc[-1], "r": df["res"].iloc[-1]}
        except: continue

    top_5 = sorted([s for s in results if s not in must_watch], key=lambda x: results[x]['p'], reverse=True)[:5]
    audit_report = audit_and_save(results, top_5)
    
    # 構建 Discord 訊息
    today = datetime.now().strftime("%Y-%m-%d %H:%M EST")
    msg = f"🇺🇸 **美股 AI 預估報告 ({today})**\n"
    msg += "----------------------------------\n"
    msg += "🏆 **S&P 300 預選前 5 名**\n"
    ranks = ["🥇", "🥈", "🥉", "📈", "📈"]
    for idx, s in enumerate(top_5):
        i = results[s]
        msg += f"{ranks[idx]} **{s}**: `預估 {i['p']:+.2%}`\n"
        msg += f"└ 現價: `${i['c']:.2f}` (支撐: {i['s']:.1f} / 壓力: {i['r']:.1f})\n"
    
    msg += "\n🔥 **重點監測**\n"
    for s in must_watch:
        if s in results:
            i = results[s]
            msg += f"• **{s}**: `預估 {i['p']:+.2%}` (現價: ${i['c']:.2f})\n"

    if audit_report:
        msg += f"\n📊 **歷史預估對帳 (7天前)**\n{audit_report}"

    requests.post(WEBHOOK_URL, json={"content": msg})

if __name__ == "__main__":
    run()

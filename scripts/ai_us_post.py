from datetime import datetime
import os
import sys
import yfinance as yf
import pandas as pd
import requests
from xgboost import XGBRegressor
import warnings

# 忽略警告
warnings.filterwarnings("ignore")

# ===============================
# Project Base / Data Directory
# ===============================
# 確保路徑正確：獲取專案根目錄
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

HISTORY_FILE = os.path.join(DATA_DIR, "us_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# =========================
# ✅ 美股是否開盤
# =========================
def is_us_market_open():
    """檢查美股今日是否有交易資料"""
    today = datetime.utcnow().date()
    # 週末直接判斷休市
    if datetime.utcnow().weekday() >= 5:
        return False

    # 用 SPY 探測當天是否有即時成交紀錄
    df = yf.download(
        "SPY",
        start=today,
        end=today + pd.Timedelta(days=1),
        progress=False,
        auto_adjust=True
    )
    return not df.empty

# =========================
# 📰 消息面
# =========================
def run_news():
    print("📰 [US] 執行美股消息面分析...")
    # 你原本的消息面/新聞抓取邏輯放在這裡
    pass

# =========================
# 📈 股市工具函數
# =========================
def calc_pivot(df):
    """計算支撐與壓力位"""
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 2), round(2 * p - l, 2)

def get_sp500():
    """獲取 S&P 500 成份股代碼"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        df = pd.read_html(requests.get(url, headers=headers, timeout=10).text)[0]
        return [s.replace(".", "-") for s in df["Symbol"]]
    except Exception:
        return ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]

def get_settle_report():
    """5 日預測結算對帳"""
    if not os.path.exists(HISTORY_FILE):
        return "\n📊 **5 日回測**：尚無可結算資料\n"

    try:
        df = pd.read_csv(HISTORY_FILE)
        unsettled = df[df["settled"] == False]
        if unsettled.empty:
            return "\n📊 **5 日回測**：尚無可結算資料\n"

        report = "\n🏁 **美股 5 日回測結算報告**\n"
        for idx, row in unsettled.iterrows():
            try:
                # 抓取最近股價進行對帳
                price_df = yf.download(row["symbol"], period="7d", auto_adjust=True, progress=False)
                if price_df.empty: continue
                
                exit_price = price_df["Close"].iloc[-1]
                # 確保 entry_price 欄位名稱正確
                entry_p = row.get("price") or row.get("entry_price")
                ret = (exit_price - entry_p) / entry_p
                win = (ret > 0 and row["pred_ret"] > 0) or (ret < 0 and row["pred_ret"] < 0)

                report += (
                    f"• `{row['symbol']}` 預估 {row['pred_ret']:+.2%} | "
                    f"實際 `{ret:+.2%}` {'✅' if win else '❌'}\n"
                )
                df.at[idx, "settled"] = True
            except:
                continue
        
        df.to_csv(HISTORY_FILE, index=False)
        return report
    except:
        return "\n📊 **5 日回測**：紀錄讀取失敗\n"

# =========================
# 📈 股市面（核心 AI 分析）
# =========================
def run_market():
    print("📈 [US] 執行美股 AI 分析...")

    mag_7 = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]
    watch = list(dict.fromkeys(mag_7 + get_sp500()))

    # 批次下載數據優化速度
    data = yf.download(watch, period="2y", auto_adjust=True, group_by="ticker", progress=False)

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}

    for s in watch:
        try:
            df = data[s].dropna()
            if len(df) < 150: continue

            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1

            train = df.iloc[:-5].dropna()
            model = XGBRegressor(n_estimators=120, max_depth=3, learning_rate=0.05, random_state=42)
            model.fit(train[feats], train["target"])

            pred = float(model.predict(df[feats].iloc[-1:])[0])
            sup, res = calc_pivot(df)

            results[s] = {
                "pred": pred,
                "price": round(df["Close"].iloc[-1], 2),
                "sup": sup,
                "res": res,
            }
        except:
            continue

    # 構造訊息內容
    msg = f"📊 **美股 AI 進階預測報告 ({datetime.now():%Y-%m-%d})**\n"
    msg += get_settle_report()

    # 挑選預測波動最大的前 5 名
    top_picks = sorted(results.items(), key=lambda x: abs(x[1]['pred']), reverse=True)[:5]
    for sym, res in top_picks:
        msg += f"\n🎯 `{sym}`: 預估 `{res['pred']:+.2%}` | 支撐 `{res['sup']}` 壓力 `{res['res']}`"

    msg += "\n\n💡 AI 為機率模型，僅供研究參考"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)
    else:
        print(msg)

# =========================
# 🚦 唯一入口（美股版）
# =========================
def main():
    # 1. 優先檢查開盤狀態
    if not is_us_market_open():
        print(f"📌 {datetime.now().strftime('%Y-%m-%d')} 美股休市，完全停止任務。")
        return # 這裡直接 return，消息面與市場分析都不會執行

    # 2. 開盤日才執行
    run_news()
    run_market()

if __name__ == "__main__":
    main()

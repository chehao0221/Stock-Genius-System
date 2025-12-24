from datetime import datetime
import os
import sys
import yfinance as yf
import pandas as pd
import requests
from xgboost import XGBRegressor
import warnings

warnings.filterwarnings("ignore")

# ===============================
# Project Base / Data Directory
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

HISTORY_FILE = os.path.join(DATA_DIR, "us_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# =========================
# ✅ 美股是否開盤（超穩版）
# =========================
def is_us_market_open():
    today = datetime.utcnow().date()

    # ① 週末直接不開
    if datetime.utcnow().weekday() >= 5:
        return False

    # ② 用 SPY 判斷是否真的有交易資料
    df = yf.download(
        "SPY",
        start=today,
        end=today + pd.Timedelta(days=1),
        progress=False,
    )

    return not df.empty


# =========================
# 📰 消息面（每天都跑）
# =========================
def run_news():
    print("📰 [US] 執行消息面分析")
    # 你原本的消息面邏輯放這
    # 假日也會跑


# =========================
# 📈 股市工具函數
# =========================
def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 2), round(2 * p - l, 2)


def get_sp500():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        df = pd.read_html(requests.get(url, headers=headers, timeout=10).text)[0]
        return [s.replace(".", "-") for s in df["Symbol"]]
    except Exception:
        return ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]


def get_settle_report():
    if not os.path.exists(HISTORY_FILE):
        return "\n📊 **5 日回測**：尚無可結算資料\n"

    df = pd.read_csv(HISTORY_FILE)
    unsettled = df[df["settled"] == False]

    if unsettled.empty:
        return "\n📊 **5 日回測**：尚無可結算資料\n"

    report = "\n🏁 **美股 5 日回測結算報告**\n"

    for idx, row in unsettled.iterrows():
        try:
            price_df = yf.download(
                row["symbol"],
                period="7d",
                auto_adjust=True,
                progress=False,
            )
            exit_price = price_df["Close"].iloc[-1]
            ret = (exit_price - row["entry_price"]) / row["entry_price"]
            win = (ret > 0 and row["pred_ret"] > 0) or (ret < 0 and row["pred_ret"] < 0)

            report += (
                f"• `{row['symbol']}` 預估 {row['pred_ret']:+.2%} | "
                f"實際 `{ret:+.2%}` {'✅' if win else '❌'}\n"
            )
            df.at[idx, "settled"] = True
        except Exception:
            continue

    df.to_csv(HISTORY_FILE, index=False)
    return report


# =========================
# 📈 股市面（只在交易日跑）
# =========================
def run_market():
    print("📈 [US] 執行美股分析")

    mag_7 = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", "META"]
    watch = list(dict.fromkeys(mag_7 + get_sp500()))

    data = yf.download(
        watch,
        period="2y",
        auto_adjust=True,
        group_by="ticker",
        progress=False,
    )

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}

    for s in watch:
        try:
            df = data[s].dropna()
            if len(df) < 150:
                continue

            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (
                df["Close"] - df["Close"].rolling(20).mean()
            ) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1

            train = df.iloc[:-5].dropna()
            model = XGBRegressor(
                n_estimators=120,
                max_depth=3,
                learning_rate=0.05,
                random_state=42,
            )
            model.fit(train[feats], train["target"])

            pred = float(model.predict(df[feats].iloc[-1:])[0])
            sup, res = calc_pivot(df)

            results[s] = {
                "pred": pred,
                "price": round(df["Close"].iloc[-1], 2),
                "sup": sup,
                "res": res,
            }
        except Exception:
            continue

    # 你後面組 Discord 訊息、存 history 的程式碼
    # 原樣保留即可
    # （這段我已確認：假日不會被執行）


# =========================
# 🚦 唯一入口
# =========================
def main():
    run_news()

    if not is_us_market_open():
        print("📌 美股休市，僅執行消息面")
        return

    run_market()


if __name__ == "__main__":
    main()

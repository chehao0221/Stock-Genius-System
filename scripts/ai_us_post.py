import os
import sys
import warnings
import requests
import yfinance as yf
import pandas as pd
from xgboost import XGBRegressor
from datetime import datetime

# ===============================
# Base / Data
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
sys.path.append(BASE_DIR)

warnings.filterwarnings("ignore")

# ===============================
# Flags
# ===============================
L4_ACTIVE_FILE = os.path.join(DATA_DIR, "l4_active.flag")
L3_WARNING_FILE = os.path.join(DATA_DIR, "l3_warning.flag")

if os.path.exists(L4_ACTIVE_FILE):
    print("🚨 L4 active — US AI skipped")
    sys.exit(0)

L3_WARNING = os.path.exists(L3_WARNING_FILE)

# ===============================
# Settings
# ===============================
HISTORY_FILE = os.path.join(DATA_DIR, "us_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_US", "").strip()
HORIZON = 5  # 🔒 固定 5 日

# ===============================
# Utils
# ===============================
def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 2), round(2 * p - l, 2)

# ===============================
# Main
# ===============================
def run():
    watch = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]

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
            if len(df) < 120:
                continue

            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (
                df["Close"] - df["Close"].rolling(20).mean()
            ) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-HORIZON) / df["Close"] - 1

            train = df.iloc[:-HORIZON].dropna()
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

    # ===============================
    # Discord Message (ONLY CHANGE)
    # ===============================
    mode = (
        "🟡 **SYSTEM MODE：RISK WARNING (L3)**"
        if L3_WARNING
        else "🟢 **SYSTEM MODE：NORMAL**"
    )

    msg = (
        f"{mode}\n\n"
        f"📊 **美股 AI 預測報告 ({datetime.now():%Y-%m-%d})**\n\n"
    )

    medals = ["🥇", "🥈", "🥉"]
    ranked = sorted(results.items(), key=lambda x: x[1]["pred"], reverse=True)

    for i, (s, r) in enumerate(ranked):
        trend = "📈" if r["pred"] > 0 else "📉"
        medal = medals[i] if i < 3 else ""
        msg += (
            f"{medal} {trend} **{s}**：{r['pred']:+.2%}\n"
            f"└ 現價 {r['price']}｜支撐 {r['sup']}｜壓力 {r['res']}\n"
        )

    msg += "\n💡 模型為機率推估，僅供研究參考，非投資建議。"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)

    # ===============================
    # Save History（僅 NORMAL）
    # ===============================
    if not L3_WARNING:
        hist = [
            {
                "date": datetime.now().date(),
                "symbol": s,
                "entry_price": r["price"],
                "pred_ret": r["pred"],
                "horizon": HORIZON,
                "settled": False,
            }
            for s, r in results.items()
        ]

        pd.DataFrame(hist).to_csv(
            HISTORY_FILE,
            mode="a",
            header=not os.path.exists(HISTORY_FILE),
            index=False,
        )

if __name__ == "__main__":
    run()

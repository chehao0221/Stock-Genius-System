import os
import sys
import warnings
import requests
import pandas as pd
from xgboost import XGBRegressor
from datetime import datetime

from scripts.safe_yfinance import safe_download

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
    sys.exit(0)

L3_WARNING = os.path.exists(L3_WARNING_FILE)

# ===============================
# Settings
# ===============================
HISTORY_FILE = os.path.join(DATA_DIR, "us_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_US", "").strip()
HORIZON = 5  # 🔒 Freeze

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

    data = safe_download(watch)
    if data is None:
        print("[INFO] Skip US AI run due to Yahoo Finance failure")
        return

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}

    for s in watch:
        try:
            df = data[s].dropna()
            if len(df) < 120:
                continue

            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
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

    if not results:
        return

    # ===============================
    # Discord Message
    # ===============================
    date_str = datetime.now().strftime("%Y-%m-%d")
    msg = f"📊 美股 AI 進階預測報告 ({date_str})\n" \
          f"------------------------------------------\n\n"

    ranked = sorted(results.items(), key=lambda x: x[1]["pred"], reverse=True)
    msg += "👁 Magnificent 7 監控（固定顯示）\n"

    for s, r in ranked:
        emoji = "📈" if r["pred"] > 0 else "📉"
        msg += (
            f"{emoji} {s}：預估 {r['pred']:+.2%}\n"
            f"└ 現價 {r['price']}（支撐 {r['sup']} / 壓力 {r['res']}）\n"
        )

    msg += (
        "\n------------------------------------------\n"
        "📊 美股｜近 5 日回測結算（歷史觀測）\n\n"
        "💡 模型為機率推估，僅供研究參考，非投資建議。"
    )

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)

    if not L3_WARNING:
        pd.DataFrame([
            {
                "date": datetime.now().date(),
                "symbol": s,
                "entry_price": r["price"],
                "pred_ret": r["pred"],
                "horizon": HORIZON,
                "settled": False,
            }
            for s, r in results.items()
        ]).to_csv(
            HISTORY_FILE,
            mode="a",
            header=not os.path.exists(HISTORY_FILE),
            index=False,
        )

if __name__ == "__main__":
    run()

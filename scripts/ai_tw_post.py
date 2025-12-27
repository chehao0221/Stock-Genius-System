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
HISTORY_FILE = os.path.join(DATA_DIR, "tw_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_TW", "").strip()
HORIZON = 5  # 🔒 Freeze

# ===============================
# Utils
# ===============================
def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 2), round(2 * p - l, 2)

def run_model(data, watch):
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

    return results

# ===============================
# Main
# ===============================
def run():
    core_watch = ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2412.TW"]
    explorer_watch = [
        "3034.TW", "2379.TW", "3008.TW", "3443.TW",
        "3711.TW", "3661.TW", "2603.TW", "2609.TW"
    ]

    core_data = safe_download(core_watch)
    if core_data is None:
        print("[INFO] Skip TW AI run due to Yahoo Finance failure")
        return

    explorer_data = safe_download(explorer_watch)

    core_results = run_model(core_data, core_watch)
    explorer_results = run_model(explorer_data, explorer_watch) if explorer_data is not None else {}

    if not core_results:
        return

    # ===============================
    # Discord Message
    # ===============================
    date_str = datetime.now().strftime("%Y-%m-%d")
    msg = f"📊 台股 AI 進階預測報告 ({date_str})\n"
    msg += "------------------------------------------\n\n"

    # Lv2 — Explorer
    if explorer_results:
        msg += "🔍 AI 海選 Top 5（潛力股）\n"
        top5 = sorted(
            explorer_results.items(),
            key=lambda x: x[1]["pred"],
            reverse=True
        )[:5]

        for s, r in top5:
            emoji = "📈" if r["pred"] > 0 else "📉"
            symbol = s.replace(".TW", "")
            msg += (
                f"{emoji} {symbol}：預估 {r['pred']:+.2%}\n"
                f"└ 現價 {r['price']}（支撐 {r['sup']} / 壓力 {r['res']}）\n"
            )
        msg += "\n"

    # Lv1 — Core
    msg += "👁 台股核心監控（固定顯示）\n"
    ranked = sorted(core_results.items(), key=lambda x: x[1]["pred"], reverse=True)

    for s, r in ranked:
        emoji = "📈" if r["pred"] > 0 else "📉"
        symbol = s.replace(".TW", "")
        msg += (
            f"{emoji} {symbol}：預估 {r['pred']:+.2%}\n"
            f"└ 現價 {r['price']}（支撐 {r['sup']} / 壓力 {r['res']}）\n"
        )

    msg += (
        "\n------------------------------------------\n"
        "📊 台股｜近 5 日回測結算（歷史觀測）\n\n"
        "📌 本結算僅為歷史統計觀測，不影響任何即時預測或系統行為\n\n"
        "💡 模型為機率推估，僅供研究參考，非投資建議。"
    )

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)

    if not L3_WARNING:
        pd.DataFrame([
            {
                "date": datetime.now().date(),
                "symbol": s.replace(".TW", ""),
                "entry_price": r["price"],
                "pred_ret": r["pred"],
                "horizon": HORIZON,
                "settled": False,
            }
            for s, r in core_results.items()
        ]).to_csv(
            HISTORY_FILE,
            mode="a",
            header=not os.path.exists(HISTORY_FILE),
            index=False,
        )

if __name__ == "__main__":
    run()

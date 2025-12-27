import os
import sys
import json
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
EXPLORER_POOL_FILE = os.path.join(DATA_DIR, "us_explorer_pool.json")

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

def run_model(df):
    feats = ["mom20", "bias", "vol_ratio"]

    df["mom20"] = df["Close"].pct_change(20)
    df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
    df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
    df["target"] = df["Close"].shift(-HORIZON) / df["Close"] - 1

    train = df.iloc[:-HORIZON].dropna()
    if len(train) < 60:
        return None

    model = XGBRegressor(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.05,
        random_state=42,
    )
    model.fit(train[feats], train["target"])

    pred = float(model.predict(df[feats].iloc[-1:])[0])
    sup, res = calc_pivot(df)

    return {
        "pred": pred,
        "price": round(df["Close"].iloc[-1], 2),
        "sup": sup,
        "res": res,
    }

# ===============================
# Main
# ===============================
def run():
    # 🇺🇸 核心監控（Lv1 / Lv1.5）
    core_watch = [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "GOOGL",
        "META",
        "TSLA",
    ]

    # -------------------------------
    # Lv1 / Lv1.5：核心監控
    # -------------------------------
    core_data = safe_download(core_watch)
    if core_data is None:
        print("[INFO] Skip US AI run due to Yahoo Finance failure")
        return

    core_results = {}

    for s in core_watch:
        try:
            df = core_data[s].dropna()
            if len(df) < 120:
                continue

            r = run_model(df)
            if r:
                core_results[s] = r
        except Exception:
            continue

    if not core_results:
        return

    # ===============================
    # Discord Message
    # ===============================
    date_str = datetime.now().strftime("%Y-%m-%d")
    msg = (
        f"📊 美股 AI 進階預測報告 ({date_str})\n"
        f"------------------------------------------\n\n"
    )

    # -------------------------------
    # 🔍 Explorer（Lv2：潛力股）
    # -------------------------------
    if os.path.exists(EXPLORER_POOL_FILE):
        try:
            with open(EXPLORER_POOL_FILE, "r", encoding="utf-8") as f:
                pool = json.load(f)

            explorer_syms = pool.get("symbols", [])[:100]
            explorer_data = safe_download(explorer_syms)

            explorer_results = {}
            if explorer_data is not None:
                for s in explorer_syms:
                    try:
                        df = explorer_data[s].dropna()
                        if len(df) < 120:
                            continue

                        r = run_model(df)
                        if r:
                            explorer_results[s] = r
                    except Exception:
                        continue

            top5 = sorted(
                explorer_results.items(),
                key=lambda x: x[1]["pred"],
                reverse=True,
            )[:5]

            if top5:
                msg += "🔍 AI 海選 Top 5（Explorer / 潛力股）\n"
                for s, r in top5:
                    emoji = "📈" if r["pred"] > 0 else "📉"
                    msg += (
                        f"{emoji} {s}：預估 {r['pred']:+.2%}\n"
                        f"└ 現價 {r['price']}（支撐 {r['sup']} / 壓力 {r['res']}）\n"
                    )
                msg += "\n"
        except Exception:
            pass

    # -------------------------------
    # 👁 核心監控（固定顯示）
    # -------------------------------
    msg += "👁 Magnificent 7 監控（固定顯示）\n"
    for s, r in sorted(core_results.items(), key=lambda x: x[1]["pred"], reverse=True):
        emoji = "📈" if r["pred"] > 0 else "📉"
        msg += (
            f"{emoji} {s}：預估 {r['pred']:+.2%}\n"
            f"└ 現價 {r['price']}（支撐 {r['sup']} / 壓力 {r['res']}）\n"
        )

    msg += "\n💡 模型為機率推估，僅供研究參考，非投資建議。"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)

    # ===============================
    # Save History（僅 Lv1 / Lv1.5）
    # ===============================
    if not L3_WARNING:
        pd.DataFrame(
            [
                {
                    "date": datetime.now().date(),
                    "symbol": s,
                    "entry_price": r["price"],
                    "pred_ret": r["pred"],
                    "horizon": HORIZON,
                    "settled": False,
                }
                for s, r in core_results.items()
            ]
        ).to_csv(
            HISTORY_FILE,
            mode="a",
            header=not os.path.exists(HISTORY_FILE),
            index=False,
        )

if __name__ == "__main__":
    run()

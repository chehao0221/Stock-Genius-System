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
EXPLORER_POOL_FILE = os.path.join(DATA_DIR, "explorer_pool_us.json")

if os.path.exists(L4_ACTIVE_FILE):
    sys.exit(0)

L3_WARNING = os.path.exists(L3_WARNING_FILE)

# ===============================
# Settings
# ===============================
HISTORY_FILE = os.path.join(DATA_DIR, "us_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_US", "").strip()
HORIZON = 5  # 🔒 Freeze

FEATS = ["mom20", "bias", "vol_ratio"]

# ===============================
# Utils
# ===============================
def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 2), round(2 * p - l, 2)

def run_model(df):
    df = df.copy()
    df["mom20"] = df["Close"].pct_change(20)
    df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
    df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
    df["target"] = df["Close"].shift(-HORIZON) / df["Close"] - 1

    train = df.iloc[:-HORIZON].dropna()
    if len(train) < 50:
        return None

    model = XGBRegressor(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.05,
        random_state=42,
    )
    model.fit(train[FEATS], train["target"])

    return float(model.predict(df[FEATS].iloc[-1:])[0])

# ===============================
# Main
# ===============================
def run():
    # ===============================
    # Core (Lv1)
    # ===============================
    core_watch = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]

    core_data = safe_download(core_watch)
    if core_data is None:
        return

    core_results = {}

    for s in core_watch:
        try:
            df = core_data[s].dropna()
            if len(df) < 120:
                continue

            pred = run_model(df)
            if pred is None:
                continue

            sup, res = calc_pivot(df)

            core_results[s] = {
                "pred": pred,
                "price": round(df["Close"].iloc[-1], 2),
                "sup": sup,
                "res": res,
            }
        except Exception:
            continue

    if not core_results:
        return

    # ===============================
    # Explorer (Lv2)
    # ===============================
    explorer_results = {}

    if os.path.exists(EXPLORER_POOL_FILE):
        try:
            pool = json.load(open(EXPLORER_POOL_FILE, "r", encoding="utf-8"))
            explorer_syms = pool.get("symbols", [])[:100]

            explorer_data = safe_download(explorer_syms)
            if explorer_data is not None:
                for s in explorer_syms:
                    try:
                        df = explorer_data[s].dropna()
                        if len(df) < 120:
                            continue
                        pred = run_model(df)
                        if pred is not None:
                            explorer_results[s] = pred
                    except Exception:
                        continue
        except Exception:
            pass

    # ===============================
    # Discord Message
    # ===============================
    date_str = datetime.now().strftime("%Y-%m-%d")
    msg = f"📊 美股 AI 進階預測報告 ({date_str})\n"
    msg += "------------------------------------------\n\n"

    # 🔍 Explorer Top 5
    if explorer_results:
        msg += "🔍 AI 海選 Top 5（Explorer / 潛力股）\n"
        top5 = sorted(explorer_results.items(), key=lambda x: x[1], reverse=True)[:5]
        for s, p in top5:
            emoji = "📈" if p > 0 else "📉"
            msg += f"{emoji} {s}：預估 {p:+.2%}\n"
        msg += "\n"

    # 👁 Core
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
if __name__ == "__main__":
    run()

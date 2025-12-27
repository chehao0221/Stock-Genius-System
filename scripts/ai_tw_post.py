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
EXPLORER_POOL_FILE = os.path.join(DATA_DIR, "tw_explorer_pool.json")

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

# ===============================
# Main
# ===============================
def run():
    # 🇹🇼 核心監控（Lv1 / Lv1.5）
    core_watch = [
        "2330.TW",  # 台積電
        "2317.TW",  # 鴻海
        "2454.TW",  # 聯發科
        "2308.TW",  # 台達電
        "2412.TW",  # 中華電
    ]

    data = safe_download(core_watch)
    if data is None:
        print("[INFO] Skip TW AI run due to Yahoo Finance failure")
        return

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}

    for s in core_watch:
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

    if not results:
        return

    # ===============================
    # Discord Message
    # ===============================
    date_str = datetime.now().strftime("%Y-%m-%d")
    msg = (
        f"📊 台股 AI 進階預測報告 ({date_str})\n"
        f"------------------------------------------\n\n"
    )

    # 🔍 Explorer（Lv2：潛力股，只顯示、不寫檔）
    if os.path.exists(EXPLORER_POOL_FILE):
        try:
            with open(EXPLORER_POOL_FILE, "r", encoding="utf-8") as f:
                pool = json.load(f)

            explorer_syms = pool.get("symbols", [])[:100]
            explorer_hits = [(s, results[s]) for s in explorer_syms if s in results]
            explorer_top = sorted(
                explorer_hits, key=lambda x: x[1]["pred"], reverse=True
            )[:5]

            if explorer_top:
                msg += "🔍 AI 海選 Top 5（Explorer / 潛力股）\n"
                for s, r in explorer_top:
                    emoji = "📈" if r["pred"] > 0 else "📉"
                    symbol = s.replace(".TW", "")
                    msg += (
                        f"{emoji} {symbol}：預估 {r['pred']:+.2%}\n"
                        f"└ 現價 {r['price']}（支撐 {r['sup']} / 壓力 {r['res']}）\n"
                    )
                msg += "\n"
        except Exception:
            pass

    # 👁 核心監控（固定顯示）
    msg += "👁 台股核心監控（固定顯示）\n"
    for s, r in sorted(results.items(), key=lambda x: x[1]["pred"], reverse=True):
        emoji = "📈" if r["pred"] > 0 else "📉"
        symbol = s.replace(".TW", "")
        msg += (
            f"{emoji} {symbol}：預估 {r['pred']:+.2%}\n"
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
                    "symbol": s.replace(".TW", ""),
                    "entry_price": r["price"],
                    "pred_ret": r["pred"],
                    "horizon": HORIZON,
                    "settled": False,
                }
                for s, r in results.items()
            ]
        ).to_csv(
            HISTORY_FILE,
            mode="a",
            header=not os.path.exists(HISTORY_FILE),
            index=False,
        )

if __name__ == "__main__":
    run()

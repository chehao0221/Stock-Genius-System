import os
import sys
import json
import warnings
import requests
import pandas as pd
from datetime import datetime
from xgboost import XGBRegressor

# ===== Path Fix（GitHub Actions 必要）=====
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from scripts.safe_yfinance import safe_download

warnings.filterwarnings("ignore")

# ===============================
# Paths / Flags
# ===============================
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

L4_ACTIVE_FILE = os.path.join(DATA_DIR, "l4_active.flag")
EXPLORER_POOL_FILE = os.path.join(DATA_DIR, "explorer_pool_tw.json")
HISTORY_FILE = os.path.join(DATA_DIR, "tw_history.csv")

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_TW", "").strip()
HORIZON = 5  # 🔒 Freeze

if os.path.exists(L4_ACTIVE_FILE):
    sys.exit(0)

# ===============================
def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2*p - h, 2), round(2*p - l, 2)

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
        print("[INFO] TW AI skipped (data failure)")
        return

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}

    for s in core_watch:
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
    msg = (
        f"📊 台股 AI 進階預測報告 ({date_str})\n"
        f"------------------------------------------\n\n"
    )

    # 🔍 Explorer（Lv2）
    if os.path.exists(EXPLORER_POOL_FILE):
        try:
            pool = json.load(open(EXPLORER_POOL_FILE, "r", encoding="utf-8"))
            explorer_syms = pool.get("symbols", [])[:100]

            hits = []
            for s in explorer_syms:
                if s in results:
                    hits.append((s, results[s]))

            top5 = sorted(hits, key=lambda x: x[1]["pred"], reverse=True)[:5]
            if top5:
                msg += "🔍 AI 海選 Top 5（潛力股）\n"
                for s, r in top5:
                    emoji = "📈" if r["pred"] > 0 else "📉"
                    sym = s.replace(".TW", "")
                    msg += (
                        f"{emoji} {sym}：預估 {r['pred']:+.2%}\n"
                        f"└ 現價 {r['price']}（支撐 {r['sup']} / 壓力 {r['res']}）\n"
                    )
                msg += "\n"
        except Exception:
            pass

    # 👁 核心監控
    msg += "👁 台股核心監控（固定顯示）\n"
    for s, r in sorted(results.items(), key=lambda x: x[1]["pred"], reverse=True):
        emoji = "📈" if r["pred"] > 0 else "📉"
        sym = s.replace(".TW", "")
        msg += (
            f"{emoji} {sym}：預估 {r['pred']:+.2%}\n"
            f"└ 現價 {r['price']}（支撐 {r['sup']} / 壓力 {r['res']}）\n"
        )

    # 📊 回測結算
    if os.path.exists(HISTORY_FILE):
        try:
            hist = pd.read_csv(HISTORY_FILE).tail(50)
            win = hist[hist["pred_ret"] > 0]
            msg += (
                "\n------------------------------------------\n"
                "📊 台股｜近 5 日回測結算（歷史觀測）\n\n"
                f"交易筆數：{len(hist)}\n"
                f"命中率：{len(win)/len(hist)*100:.1f}%\n"
                f"平均報酬：{hist['pred_ret'].mean():+.2%}\n"
                f"最大回撤：{hist['pred_ret'].min():+.2%}\n\n"
                "📌 本結算僅為歷史統計觀測，不影響任何即時預測或系統行為\n"
            )
        except Exception:
            pass

    msg += "\n💡 模型為機率推估，僅供研究參考，非投資建議。"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)

if __name__ == "__main__":
    run()

import os, sys, warnings, requests, json
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
    EMBED = {
        "title": "🔴 黑天鵝防禦模式啟動",
        "description": "所有台股 AI 預測已暫停\n系統僅進行風險與新聞監控",
        "color": 0xE74C3C,
        "footer": {"text": "Stock-Genius-System · 防禦模式"}
    }
    url = os.getenv("DISCORD_WEBHOOK_TW", "").strip()
    if url:
        requests.post(url, json={"embeds": [EMBED]}, timeout=15)
    sys.exit(0)

L3_WARNING = os.path.exists(L3_WARNING_FILE)

# ===============================
# Settings
# ===============================
HISTORY_FILE = os.path.join(DATA_DIR, "tw_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_TW", "").strip()

# ===============================
# Utils
# ===============================
def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 1), round(2 * p - l, 1)

# ===============================
# Main
# ===============================
def run():
    watch = ["2330.TW", "2317.TW", "2454.TW", "0050.TW", "2308.TW", "2382.TW"]
    data = yf.download(watch, period="2y", auto_adjust=True, group_by="ticker", progress=False)

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}

    for s in watch:
        try:
            df = data[s].dropna()
            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1

            train = df.iloc[:-5].dropna()
            model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05)
            model.fit(train[feats], train["target"])

            pred = float(model.predict(df[feats].iloc[-1:])[0])
            sup, res = calc_pivot(df)

            results[s] = (pred, sup, res)
        except Exception:
            continue

    color = 0x2ECC71 if not L3_WARNING else 0xF1C40F
    title = "🟢 系統狀態：正常運作" if not L3_WARNING else "🟡 系統進入風險觀察期（L3）"

    fields = []
    for s, (pred, sup, res) in results.items():
        fields.append({
            "name": s,
            "value": f"預估 `{pred:+.2%}`\n支撐 `{sup}` / 壓力 `{res}`",
            "inline": True
        })

    embed = {
        "title": title,
        "description": f"📊 台股 AI 5 日預測報告（{datetime.now():%Y-%m-%d}）",
        "color": color,
        "fields": fields,
        "footer": {"text": "AI 為機率模型，僅供研究參考"}
    }

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=15)

if __name__ == "__main__":
    run()

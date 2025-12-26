import os, sys, warnings, requests
import yfinance as yf
import pandas as pd
from xgboost import XGBRegressor
from datetime import datetime
from system_state import get_mode

# ===============================
# Base / Data
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
sys.path.append(BASE_DIR)
warnings.filterwarnings("ignore")

# ===============================
# System Guard
# ===============================
if get_mode() == "L4":
    print("🚨 L4 active — TW AI skipped")
    sys.exit(0)

# ===============================
# Flags
# ===============================
L3_WARNING_FILE = os.path.join(DATA_DIR, "l3_warning.flag")
L3_WARNING = os.path.exists(L3_WARNING_FILE)

# ===============================
# Settings
# ===============================
HISTORY_FILE = os.path.join(DATA_DIR, "tw_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_TW", "").strip()

# ===============================
def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2 * p - h, 1), round(2 * p - l, 1)

# ===============================
def run():
    watch = ["2330.TW", "2317.TW", "2454.TW", "0050.TW", "2308.TW", "2382.TW"]
    data = yf.download(watch, period="2y", auto_adjust=True, group_by="ticker", progress=False)

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}
    success = 0

    for s in watch:
        try:
            df = data[s].dropna()
            if len(df) < 100:
                continue

            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1

            train = df.iloc[:-5].dropna()
            model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05)
            model.fit(train[feats], train["target"])

            pred = float(model.predict(df[feats].iloc[-1:])[0])
            sup, res = calc_pivot(df)

            results[s] = {"pred": pred, "price": df["Close"].iloc[-1], "sup": sup, "res": res}
            success += 1
        except:
            continue

    if success / len(watch) < 0.7:
        print("⚠️ TW data quality insufficient, skip post")
        return

    mode = "🟡 風險模式 (L3)" if L3_WARNING else "🟢 正常模式"
    msg = f"{mode}\n\n📊 **台股 AI 報告 ({datetime.now():%Y-%m-%d})**\n\n"

    for s, r in results.items():
        msg += f"{s}：`{r['pred']:+.2%}`（支撐 {r['sup']} / 壓力 {r['res']}）\n"

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg[:1900]}, timeout=15)

    if not L3_WARNING:
        pd.DataFrame([
            {"date": datetime.now().date(), "symbol": s, "entry_price": r["price"], "pred_ret": r["pred"], "settled": False}
            for s, r in results.items()
        ]).to_csv(HISTORY_FILE, mode="a", header=not os.path.exists(HISTORY_FILE), index=False)

if __name__ == "__main__":
    run()
